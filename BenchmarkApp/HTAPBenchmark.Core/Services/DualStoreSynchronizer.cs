using System.Diagnostics;
using Dapper;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

/// <summary>
/// Periodično propagira nove OLTP redove iz Hekaton sloja (htap.*) u analitički
/// columnstore sloj (cs.*) tokom mjernog runa.
///
/// MOTIVACIJA: bez sinhronizacije dual-store konfiguracija dobiva izolaciju
/// radnih tokova besplatno — analitika čita statičan snapshot koji nikad ne
/// plaća cijenu propagacije. Produkcijski sistemi tu cijenu plaćaju kontinuirano.
/// Pokretanjem benchmarka pri više intervala dobiva se krivulja kompromisa
/// između svježine analitičkih podataka i OLTP propusnosti.
///
/// MODEL: propagacija po rasponu identifikatora. Benchmark generiše ID-ove iz
/// kontinuiranog brojača, pa je tačan raspon novih redova poznat bez skeniranja
/// tablice — svaki red se dohvaća seek-om po hash indeksu. Time je cijena ciklusa
/// proporcionalna broju novih redova, kao u delta-store modelu F1 Lightninga.
/// </summary>
public sealed class DualStoreSynchronizer
{
    private readonly string _connectionString;
    private readonly int _intervalSeconds;
    private readonly long[] _voteCounter;
    private readonly long[] _commentCounter;

    private long _lastPropagatedVoteId;
    private long _lastPropagatedCommentId;

    private readonly List<SyncCycleResult> _cycles = [];

    public IReadOnlyList<SyncCycleResult> Cycles => _cycles;

    public DualStoreSynchronizer(
        string connectionString,
        int intervalSeconds,
        long[] voteCounter,
        long[] commentCounter,
        long initialVoteId,
        long initialCommentId)
    {
        _connectionString        = connectionString;
        _intervalSeconds         = intervalSeconds;
        _voteCounter             = voteCounter;
        _commentCounter          = commentCounter;
        _lastPropagatedVoteId    = initialVoteId;
        _lastPropagatedCommentId = initialCommentId;
    }

    /// <summary>
    /// Puni htap.SyncPostIds aktivnim skupom postova i snima originalne Score
    /// vrijednosti. Poziva se prije mjernih runova kombinacije.
    /// </summary>
    public static async Task PrepareAsync(string connectionString, int[] postIds, CancellationToken ct = default)
    {
        await using var conn = new SqlConnection(connectionString);
        await conn.OpenAsync(ct);

        await conn.ExecuteAsync(new CommandDefinition(
            "TRUNCATE TABLE htap.SyncPostIds;", commandTimeout: 60, cancellationToken: ct));

        const int batchSize = 1000;
        for (int i = 0; i < postIds.Length; i += batchSize)
        {
            var values = string.Join(",", postIds.Skip(i).Take(batchSize).Select(id => $"({id})"));
            await conn.ExecuteAsync(new CommandDefinition(
                $"INSERT INTO htap.SyncPostIds (Id) VALUES {values};",
                commandTimeout: 60, cancellationToken: ct));
        }

        await conn.ExecuteAsync(new CommandDefinition(
            "EXEC htap.usp_SyncPrepare;", commandTimeout: 300, cancellationToken: ct));
    }

    /// <summary>
    /// Vraća cs.* sloj u polazno stanje: briše propagirane redove i restaurira
    /// Score vrijednosti. Poziva se nakon svakog runa u sync eksperimentu.
    /// </summary>
    public static async Task CleanupAsync(
        string connectionString, WorkloadContext ctx, CancellationToken ct = default)
    {
        await using var conn = new SqlConnection(connectionString);
        await conn.OpenAsync(ct);

        await conn.ExecuteAsync(new CommandDefinition(
            "EXEC htap.usp_SyncCleanupColumnstore @OriginalMaxVoteId, @OriginalMaxCommentId;",
            new { ctx.OriginalMaxVoteId, ctx.OriginalMaxCommentId },
            commandTimeout: 600, cancellationToken: ct));
    }

    /// <summary>
    /// Pokreće petlju sinhronizacije do isteka mjernog prozora.
    /// Ciklusi tokom warmup faze se izvršavaju (da sistem uđe u stacionarno stanje),
    /// ali se ne bilježe.
    /// </summary>
    public async Task RunAsync(DateTime warmupEnd, DateTime measureEnd, CancellationToken ct)
    {
        if (_intervalSeconds <= 0) return;

        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync(ct);

        int cycleNumber = 0;
        var sw = new Stopwatch();

        while (DateTime.UtcNow < measureEnd && !ct.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(_intervalSeconds), ct);
            }
            catch (OperationCanceledException)
            {
                break;
            }

            bool inWarmup = DateTime.UtcNow < warmupEnd;

            long toVote    = Interlocked.Read(ref _voteCounter[0]);
            long toComment = Interlocked.Read(ref _commentCounter[0]);

            long fromVote    = _lastPropagatedVoteId + 1;
            long fromComment = _lastPropagatedCommentId + 1;

            if (toVote < fromVote && toComment < fromComment) continue;

            var cycle = new SyncCycleResult
            {
                CycleNumber         = ++cycleNumber,
                SyncIntervalSeconds = _intervalSeconds
            };

            sw.Restart();
            try
            {
                var p = new DynamicParameters();
                // Ista transformacija ID-a kao u WorkloadExecutor.ExecuteOltpOperationAsync,
                // da granice raspona odgovaraju stvarno upisanim vrijednostima.
                p.Add("@FromVoteId",    (int)(fromVote    % int.MaxValue));
                p.Add("@ToVoteId",      (int)(toVote      % int.MaxValue));
                p.Add("@FromCommentId", (int)(fromComment % int.MaxValue));
                p.Add("@ToCommentId",   (int)(toComment   % int.MaxValue));
                p.Add("@VotesPropagated",    dbType: System.Data.DbType.Int32,  direction: System.Data.ParameterDirection.Output);
                p.Add("@CommentsPropagated", dbType: System.Data.DbType.Int32,  direction: System.Data.ParameterDirection.Output);
                p.Add("@PostsUpdated",       dbType: System.Data.DbType.Int32,  direction: System.Data.ParameterDirection.Output);
                p.Add("@AvgLagMs",           dbType: System.Data.DbType.Double, direction: System.Data.ParameterDirection.Output);
                p.Add("@MaxLagMs",           dbType: System.Data.DbType.Double, direction: System.Data.ParameterDirection.Output);

                await conn.ExecuteAsync(new CommandDefinition(
                    "htap.usp_SyncToColumnstore",
                    p,
                    commandType: System.Data.CommandType.StoredProcedure,
                    commandTimeout: 300,
                    cancellationToken: ct));

                sw.Stop();

                cycle.VotesPropagated    = p.Get<int>("@VotesPropagated");
                cycle.CommentsPropagated = p.Get<int>("@CommentsPropagated");
                cycle.PostsUpdated       = p.Get<int>("@PostsUpdated");
                cycle.AvgFreshnessLagMs  = p.Get<double>("@AvgLagMs");
                cycle.MaxFreshnessLagMs  = p.Get<double>("@MaxLagMs");
                cycle.DurationMs         = sw.Elapsed.TotalMilliseconds;

                _lastPropagatedVoteId    = toVote;
                _lastPropagatedCommentId = toComment;
            }
            catch (Exception ex)
            {
                sw.Stop();
                cycle.Success      = false;
                cycle.DurationMs   = sw.Elapsed.TotalMilliseconds;
                cycle.ErrorMessage = ex.Message.Length > 200 ? ex.Message[..200] : ex.Message;

                // Watermark se NE pomjera pri grešci — sljedeći ciklus ponovo pokušava
                // isti raspon. Propagacija je idempotentna (NOT EXISTS anti-join u
                // htap.usp_SyncToColumnstore), pa ponavljanje ne duplira redove niti
                // pada na narušenju primarnog ključa.
            }

            if (!inWarmup)
                _cycles.Add(cycle);
        }
    }
}
