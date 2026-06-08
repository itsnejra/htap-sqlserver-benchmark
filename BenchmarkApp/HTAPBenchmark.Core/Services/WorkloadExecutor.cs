using System.Collections.Concurrent;
using System.Diagnostics;
using Dapper;
using HTAPBenchmark.Core.Models;
using HTAPBenchmark.Core.Queries;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

public sealed class WorkloadExecutor
{
    private readonly string _connectionString;

    public WorkloadExecutor(string connectionString)
    {
        _connectionString = connectionString;
    }

    public async Task<WorkloadContext> LoadWorkloadContextAsync(string schema)
    {
        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();

        // OPTION(MAXDOP 1): prevents parallel CXSYNC_PORT stalls on memory-optimized tables
        // (im.Posts / htap.Posts are Hekaton tables; parallel ORDER BY NEWID() deadlocks).
        var postIds = (await conn.QueryAsync<int>(
            $"SELECT TOP 20000 Id FROM {schema}.Posts ORDER BY NEWID() OPTION(MAXDOP 1);",
            commandTimeout: 300)).ToArray();

        var userIds = (await conn.QueryAsync<int>(
            $"SELECT TOP 5000 Id FROM {schema}.Users ORDER BY NEWID() OPTION(MAXDOP 1);",
            commandTimeout: 300)).ToArray();

        // im/htap hash indexes make MAX(Id) a full table scan;
        // cs.* columnstore returns the same max instantly (data is identical across schemas).
        string aggSchema = (schema is "htap" or "im") ? "cs" : schema;
        int maxVoteId    = await conn.ExecuteScalarAsync<int>($"SELECT ISNULL(MAX(Id), 0) FROM {aggSchema}.Votes;",    commandTimeout: 300);
        int maxCommentId = await conn.ExecuteScalarAsync<int>($"SELECT ISNULL(MAX(Id), 0) FROM {aggSchema}.Comments;", commandTimeout: 300);

        return new WorkloadContext
        {
            PostIds           = postIds,
            UserIds           = userIds,
            NextVoteId        = maxVoteId + 1_000_000,
            NextCommentId     = maxCommentId + 1_000_000,
            OriginalMaxVoteId    = maxVoteId,
            OriginalMaxCommentId = maxCommentId
        };
    }

    /// <summary>
    /// Briše redove koje je benchmark insertovao u IM/HTAP tablice (Id > original max).
    /// Poziva se između kombinacija da se spriječi rast in-memory tablica i OOM.
    /// </summary>
    /// <summary>
    /// Zagrije OLAP buffer pool pokretanjem svih 5 OLAP query-ja jednom.
    /// Sprječava cold-cache efekt koji uzrokuje 0 OLAP ops u prvim runovima
    /// kada htap.* in-memory tablice potiskuju cs.* stranice iz buffer pool-a.
    /// </summary>
    public async Task WarmOlapCacheAsync(string schema)
    {
        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();
        foreach (var q in Queries.OlapQueries.QueryNames)
        {
            var sql = Queries.OlapQueries.GetQuery(schema, q);
            try
            {
                using var reader = await conn.ExecuteReaderAsync(
                    new CommandDefinition(sql, commandTimeout: 120));
                while (await reader.NextResultAsync()) { }
            }
            catch { /* warm-up failure nije kritičan */ }
        }
    }

    /// <summary>
    /// Čisti benchmark-insertovane redove i forsira Hekaton GC.
    /// Pri visokim razinama konkurentnosti (C>=16) UPDATE operacije na htap.Posts
    /// akumuliraju MVCC version chains brže nego standardni GC može počistiti.
    /// Rješenje: više GC poziva s dužim pauzama, proporcionalno razini konkurentnosti.
    /// </summary>
    public async Task CleanupBenchmarkDataAsync(string schema, WorkloadContext ctx, int concurrency = 4)
    {
        if (schema is not ("im" or "htap")) return;

        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();

        await BatchDeleteAsync(conn, $"{schema}.Votes",    ctx.OriginalMaxVoteId);
        await BatchDeleteAsync(conn, $"{schema}.Comments", ctx.OriginalMaxCommentId);

        // TruncateAndReloadPostsAsync resetira sve version chains između kombinacija (između
        // svake (ratio, concurrency) kombinacije). Stoga između runova unutar iste kombinacije
        // dovoljna je kratka pauza da XTP background GC obradi version chains tekućeg runa.
        // sp_xtp_checkpoint_force_garbage_collection je za durabilne tablice (checkpoint fajlovi);
        // za SCHEMA_ONLY tablice (htap.*, im.*) nema učinka — GC radi automatski u pozadini.
        // C=4:   2 poziva × 3s = 6s  | C≥16: 2 poziva × 5s = 10s
        int gcCalls        = 2;
        int gcDelaySeconds = concurrency >= 16 ? 5 : 3;

        for (int i = 0; i < gcCalls; i++)
        {
            try
            {
                // CHECKPOINT oslobađa delta store fajlove; GC čisti MVCC version chains.
                await conn.ExecuteAsync("CHECKPOINT;", commandTimeout: 30);
                await conn.ExecuteAsync(
                    "EXEC sys.sp_xtp_checkpoint_force_garbage_collection;",
                    commandTimeout: 60);
            }
            catch { /* GC/Checkpoint nisu kritični — nastavljamo */ }

            await Task.Delay(TimeSpan.FromSeconds(gcDelaySeconds));
        }
    }

    /// <summary>
    /// Resetira SAMO aktivne postove (ctx.PostIds, ~20K) u in-memory tablici:
    /// DELETE → kratka pauza (GC) → INSERT iz cs.Posts.
    ///
    /// ZAŠTO samo 20K a ne svih 3.7M:
    ///   - MVCC version chains postoje samo na redovima koje je usp_UpdatePostScore mijenjao.
    ///     Ti redovi su isključivo u skupu aktivnih postova iz WorkloadContext-a (20K).
    ///     Brisanje svih 3.7M redova stvara 3.7M tombstonova → gomila GC posao i sam po sebi
    ///     može uzrokovati OOM (7.4M GC stavki po kombinaciji × 9 kombinacija = 66M ukupno).
    ///   - Brisanje samo 20K aktivnih redova = 185× manje GC rada.
    ///
    /// Poziva se: (a) između kombinacija, i (b) između svakog runa unutar kombinacije —
    /// oba slučaja osiguravaju da version chains ne premaše kapacitet XTP GC-a.
    ///
    /// NAPOMENA: TRUNCATE TABLE nije podržan za memory-optimized tablice (SQL Error 10794).
    /// </summary>
    public async Task TruncateAndReloadPostsAsync(string schema, int[] postIds)
    {
        if (schema is not ("htap" or "im")) return;

        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();

        // Privremena tablica za ID-ove aktivnih postova (session-scoped, auto-drop on close)
        await conn.ExecuteAsync(@"
            DROP TABLE IF EXISTS #RefreshIds;
            CREATE TABLE #RefreshIds (Id INT NOT NULL PRIMARY KEY);",
            commandTimeout: 30);

        // Batch insert ID-ova u batchevima od 1000 (SQL Server podržava do ~1000 VALUES redova)
        const int batchSize = 1000;
        for (int i = 0; i < postIds.Length; i += batchSize)
        {
            var batch = postIds.Skip(i).Take(batchSize).ToArray();
            var values = string.Join(",", batch.Select(id => $"({id})"));
            await conn.ExecuteAsync($"INSERT INTO #RefreshIds (Id) VALUES {values};",
                commandTimeout: 30);
        }

        // Obriši samo aktivne postove — čisti sve MVCC version chains za te redove.
        await conn.ExecuteAsync(
            $"DELETE FROM {schema}.Posts WHERE Id IN (SELECT Id FROM #RefreshIds);",
            commandTimeout: 60);

        // Kratka pauza da XTP GC počne obrađivati tombstonove od DELETE-a.
        await Task.Delay(TimeSpan.FromSeconds(3));

        // Reload samo aktivnih postova iz cs.Posts (disk-based, uvijek konzistentan).
        // Body=NULL: RAM optimizacija.
        await conn.ExecuteAsync($@"
            INSERT INTO {schema}.Posts
                (Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,Score,ViewCount,Body,OwnerUserId,
                 LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,CommunityOwnedDate,
                 ClosedDate,Title,Tags,AnswerCount,CommentCount,FavoriteCount)
            SELECT Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,Score,ViewCount,NULL,OwnerUserId,
                 LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,CommunityOwnedDate,
                 ClosedDate,Title,Tags,AnswerCount,CommentCount,FavoriteCount
            FROM cs.Posts WITH (NOLOCK)
            WHERE Id IN (SELECT Id FROM #RefreshIds);",
            commandTimeout: 60);
    }

    /// <summary>
    /// Briše redove u batchevima od 10 000 da izbjegne timeout na velikim skupovima.
    /// Pokušava do 3 puta s pauzom od 5 s između pokušaja.
    /// </summary>
    private static async Task BatchDeleteAsync(SqlConnection conn, string table, int maxId)
    {
        const int batchSize = 10_000;
        const int maxAttempts = 3;

        for (int attempt = 1; attempt <= maxAttempts; attempt++)
        {
            try
            {
                int deleted;
                do
                {
                    deleted = await conn.ExecuteAsync(
                        $"DELETE TOP ({batchSize}) FROM {table} WHERE Id > @Max",
                        new { Max = maxId },
                        commandTimeout: 120);
                } while (deleted > 0);
                return; // uspješno završeno
            }
            catch when (attempt < maxAttempts)
            {
                await Task.Delay(TimeSpan.FromSeconds(5));
                // Reconnect u slučaju da je veza pukla
                try { await conn.CloseAsync(); await conn.OpenAsync(); } catch { /* ignore */ }
            }
        }
    }

    public async Task<List<MeasurementResult>> ExecuteRunAsync(
        DbConfiguration config,
        WorkloadRatio ratio,
        int concurrencyLevel,
        int runNumber,
        int warmupSeconds,
        int measurementSeconds,
        WorkloadContext ctx,
        int globalRunId = 0,          // globally unique run index (1-1080) — used for ID generation only
        CancellationToken cancellationToken = default)
    {
        var schema = config.ToLabel();
        var (oltpFraction, _) = ratio.GetFractions();

        int oltpThreads = Math.Max(1, (int)Math.Round(concurrencyLevel * oltpFraction));
        int olapThreads = Math.Max(1, concurrencyLevel - oltpThreads);

        var measurements = new ConcurrentBag<MeasurementResult>();
        var warmupEnd    = DateTime.UtcNow.AddSeconds(warmupSeconds);
        var measureEnd   = warmupEnd.AddSeconds(measurementSeconds);

        // runNumber (1-30) is safe because cleanup runs between every combination,
        // so ID spaces from a previous combo are gone before the next combo's run N starts.
        // globalRunId (1-1080) caused int overflow: for HTAP (runs 811-1080),
        // ctx.NextVoteId + globalRunId*10_000_000 exceeded int.MaxValue, and the
        // subsequent (int)(newId % int.MaxValue) wrap produced IDs <= OriginalMaxVoteId,
        // causing PK violations against original data rows on every HTAP insert.
        long idBase       = runNumber;
        long[] voteCounter    = [ctx.NextVoteId    + idBase * 10_000_000];
        long[] commentCounter = [ctx.NextCommentId + idBase * 10_000_000];

        var allTasks = Enumerable.Range(0, oltpThreads)
            .Select(_ => RunOltpWorkerAsync(schema, ctx, measurements, warmupEnd, measureEnd,
                voteCounter, commentCounter, runNumber, config, ratio, concurrencyLevel, cancellationToken))
            .Concat(Enumerable.Range(0, olapThreads)
            .Select(_ => RunOlapWorkerAsync(schema, measurements, warmupEnd, measureEnd,
                runNumber, config, ratio, concurrencyLevel, cancellationToken)))
            .ToList();

        await Task.WhenAll(allTasks);

        return measurements.ToList();
    }

    private async Task RunOltpWorkerAsync(
        string schema,
        WorkloadContext ctx,
        ConcurrentBag<MeasurementResult> bag,
        DateTime warmupEnd,
        DateTime measureEnd,
        long[] voteCounter,
        long[] commentCounter,
        int runNumber,
        DbConfiguration config,
        WorkloadRatio ratio,
        int concurrency,
        CancellationToken ct)
    {
        var rng = new Random(Guid.NewGuid().GetHashCode());
        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync(ct);

        var sw = new Stopwatch();

        while (DateTime.UtcNow < measureEnd && !ct.IsCancellationRequested)
        {
            bool inWarmup = DateTime.UtcNow < warmupEnd;
            string opName = OltpQueries.SelectOperationName(rng);

            sw.Restart();
            bool success = true;
            string? error = null;

            try
            {
                await ExecuteOltpOperationAsync(conn, schema, opName, ctx, rng, voteCounter, commentCounter);
            }
            catch (Exception ex)
            {
                success = false;
                error = ex.Message.Length > 200 ? ex.Message[..200] : ex.Message;
            }

            sw.Stop();

            if (!inWarmup)
            {
                bag.Add(new MeasurementResult
                {
                    Configuration    = config.ToLabel(),
                    OltpOlapRatio    = ratio.ToLabel(),
                    ConcurrencyLevel = concurrency,
                    RunNumber        = runNumber,
                    OperationType    = "OLTP",
                    OperationName    = opName,
                    StartTimestamp   = DateTime.UtcNow,
                    LatencyMs        = sw.Elapsed.TotalMilliseconds,
                    Success          = success,
                    ErrorMessage     = error
                });
            }
        }
    }

    private async Task ExecuteOltpOperationAsync(
        SqlConnection conn,
        string schema,
        string opName,
        WorkloadContext ctx,
        Random rng,
        long[] voteCounter,
        long[] commentCounter)
    {
        switch (opName)
        {
            case "usp_GetPostById":
            {
                int postId = ctx.PostIds[rng.Next(ctx.PostIds.Length)];
                await conn.ExecuteAsync(OltpQueries.GetPostById(schema), new { PostId = postId });
                break;
            }
            case "usp_GetUserById":
            {
                int userId = ctx.UserIds[rng.Next(ctx.UserIds.Length)];
                await conn.ExecuteAsync(OltpQueries.GetUserById(schema), new { UserId = userId });
                break;
            }
            case "usp_InsertVote":
            {
                long newId = Interlocked.Increment(ref voteCounter[0]);
                int postId = ctx.PostIds[rng.Next(ctx.PostIds.Length)];
                byte voteType = (byte)rng.Next(1, 4);
                int insertedId = (int)(newId % int.MaxValue);
                await conn.ExecuteAsync(OltpQueries.InsertVote(schema), new
                {
                    Id           = insertedId,
                    PostId       = postId,
                    VoteTypeId   = voteType,
                    CreationDate = DateTime.UtcNow.Date, // DateTime maps reliably; DATE param accepts it
                    UserId       = ctx.UserIds[rng.Next(ctx.UserIds.Length)]
                });
                // Enqueue za potencijalne DeleteVote operacije
                ctx.AvailableVoteIdsForDelete.Enqueue(insertedId);
                break;
            }
            case "usp_UpdatePostScore":
            {
                int postId = ctx.PostIds[rng.Next(ctx.PostIds.Length)];
                int delta  = rng.Next(0, 2) == 0 ? 1 : -1;
                await conn.ExecuteAsync(OltpQueries.UpdatePostScore(schema), new { PostId = postId, Delta = delta });
                break;
            }
            case "usp_InsertComment":
            {
                long newId = Interlocked.Increment(ref commentCounter[0]);
                int postId = ctx.PostIds[rng.Next(ctx.PostIds.Length)];
                string text = $"Benchmark comment {newId} - performance test.";
                int insertedCommentId = (int)(newId % int.MaxValue);
                await conn.ExecuteAsync(OltpQueries.InsertComment(schema), new
                {
                    Id           = insertedCommentId,
                    PostId       = postId,
                    Score        = 0,
                    Text         = text[..Math.Min(text.Length, 700)],
                    CreationDate = DateTime.UtcNow,
                    UserId       = ctx.UserIds[rng.Next(ctx.UserIds.Length)]
                });
                ctx.AvailableCommentIdsForDelete.Enqueue(insertedCommentId);
                break;
            }
            case "usp_GetRecentUserPosts":
            {
                int userId = ctx.UserIds[rng.Next(ctx.UserIds.Length)];
                await conn.ExecuteAsync(OltpQueries.GetRecentUserPosts(schema), new { UserId = userId });
                break;
            }

            // ---- DELETE operacije (dodane post-benchmark za potpuni CRUD coverage) ----

            case "usp_DeleteVote":
            {
                // Simple DELETE: briše jedan glas po PK
                // Pokušavamo dequeue iz pool-a insertovanih glasanja;
                // ako je pool prazan, preskačemo da ne bismo brisali originalne podatke.
                if (ctx.AvailableVoteIdsForDelete.TryDequeue(out int voteIdToDelete))
                {
                    await conn.ExecuteAsync(OltpQueries.DeleteVote(schema), new { Id = voteIdToDelete });
                }
                break;
            }

            case "usp_DeletePostVotes":
            {
                // Complex DELETE: briše sve glasove VoteTypeId=2 (DownVote) za nasumični post
                // Operira samo nad redovima koje je benchmark insertovao
                // (VoteTypeId=2 poklapa se s random voteType iz InsertVote)
                int postId     = ctx.PostIds[rng.Next(ctx.PostIds.Length)];
                byte voteTypeId = 2; // DownVote — najčešće za moderatorske akcije
                await conn.ExecuteAsync(OltpQueries.DeletePostVotes(schema),
                    new { PostId = postId, VoteTypeId = voteTypeId });
                break;
            }
        }
    }

    /// <summary>
    /// Dohvata snapshot CPU i RAM iskorištenosti SQL Server procesa iz DMV-ova.
    /// Koristi sys.dm_os_ring_buffers (CPU) i sys.dm_os_process_memory (RAM).
    /// Poziva se na kraju mjernog perioda svakog runa.
    /// </summary>
    public async Task<(double CpuPercent, double MemoryUsedMB)> MeasureServerResourcesAsync()
    {
        try
        {
            await using var conn = new SqlConnection(_connectionString);
            await conn.OpenAsync();

            // CPU: zadnji zapis iz ring buffer Scheduler Monitor
            const string cpuSql = @"
                SELECT TOP 1
                    record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int')
                FROM (
                    SELECT CONVERT(XML, record) AS record
                    FROM sys.dm_os_ring_buffers
                    WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
                    ORDER BY [timestamp] DESC
                ) x;";

            // RAM: radna memorija SQL Server procesa u MB
            const string ramSql = @"
                SELECT physical_memory_in_use_kb / 1024.0
                FROM sys.dm_os_process_memory;";

            double cpu = await conn.ExecuteScalarAsync<double>(cpuSql, commandTimeout: 10);
            double ram = await conn.ExecuteScalarAsync<double>(ramSql, commandTimeout: 10);
            return (Math.Round(cpu, 2), Math.Round(ram, 2));
        }
        catch
        {
            // DMV upit nije kritičan — vraćamo 0 u slučaju greške
            return (0d, 0d);
        }
    }

    private async Task RunOlapWorkerAsync(
        string schema,
        ConcurrentBag<MeasurementResult> bag,
        DateTime warmupEnd,
        DateTime measureEnd,
        int runNumber,
        DbConfiguration config,
        WorkloadRatio ratio,
        int concurrency,
        CancellationToken ct)
    {
        var rng = new Random(Guid.NewGuid().GetHashCode());

        var builder = new SqlConnectionStringBuilder(_connectionString)
        {
            CommandTimeout = 300
        };
        await using var conn = new SqlConnection(builder.ConnectionString);
        await conn.OpenAsync(ct);

        var sw = new Stopwatch();

        while (DateTime.UtcNow < measureEnd && !ct.IsCancellationRequested)
        {
            bool inWarmup = DateTime.UtcNow < warmupEnd;
            string queryName = OlapQueries.SelectQueryName(rng);
            string sql = OlapQueries.GetQuery(schema, queryName);

            // Per-query deadline: cancel the SQL command 5 s after measurement window ends.
            // This prevents slow baseline/im queries from blocking the entire run.
            var deadlineMs = (int)Math.Max(500, (measureEnd.AddSeconds(5) - DateTime.UtcNow).TotalMilliseconds);
            using var queryCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            queryCts.CancelAfter(deadlineMs);

            sw.Restart();
            bool success = true;
            string? error = null;

            try
            {
                var cmd = new CommandDefinition(sql, commandTimeout: 300,
                    cancellationToken: queryCts.Token);
                using var reader = await conn.ExecuteReaderAsync(cmd);
                while (await reader.NextResultAsync(queryCts.Token)) { }
            }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested)
            {
                // Query cancelled because measurement window ended — expected for slow schemas.
                success = false;
                error = "Query cancelled: measurement window exceeded";
                // Reopen connection so the next run on this worker is clean.
                try { await conn.CloseAsync(); await conn.OpenAsync(ct); } catch { /* ignore */ }
            }
            catch (Exception ex)
            {
                success = false;
                error = ex.Message.Length > 200 ? ex.Message[..200] : ex.Message;
            }

            sw.Stop();

            if (!inWarmup)
            {
                bag.Add(new MeasurementResult
                {
                    Configuration    = config.ToLabel(),
                    OltpOlapRatio    = ratio.ToLabel(),
                    ConcurrencyLevel = concurrency,
                    RunNumber        = runNumber,
                    OperationType    = "OLAP",
                    OperationName    = queryName,
                    StartTimestamp   = DateTime.UtcNow,
                    LatencyMs        = sw.Elapsed.TotalMilliseconds,
                    Success          = success,
                    ErrorMessage     = error
                });
            }
        }
    }
}
