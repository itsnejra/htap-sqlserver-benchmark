using System.Diagnostics;
using System.Globalization;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Logging;

namespace HTAPBenchmark.Core.Services;

public sealed class BenchmarkOrchestrator
{
    private readonly BenchmarkConfig _config;
    private readonly WorkloadExecutor _executor;
    private readonly ResultsWriter _writer;
    private readonly ILogger<BenchmarkOrchestrator> _logger;
    // Resume mapa pročitana PRIJE nego ResultsWriter otvori (i potencijalno zareze) fajlove.
    private readonly Dictionary<(string, string, int), int> _resumeMap;

    // Ukupan broj kombinacija: 4 config × 3 ratio × 3 concurrency × 30 runs = 1080
    public int TotalRuns =>
        _config.Configurations.Length *
        _config.WorkloadRatios.Length *
        _config.ConcurrencyLevels.Length *
        _config.RunsPerCombination;

    public BenchmarkOrchestrator(
        BenchmarkConfig config,
        ILogger<BenchmarkOrchestrator> logger)
    {
        _config   = config;
        _executor = new WorkloadExecutor(
            config.ConnectionString, config.OlapProcSuffix, config.CollectServerMetrics);
        _logger   = logger;
        // VAŽNO: pročitaj resume stanje PRIJE nego ResultsWriter otvori fajlove.
        // ResultsWriter koristi append:true ali drži file handle koji može spriječiti
        // konkurentno čitanje u nekim scenarijima. Čitanjem prvo garantiramo konzistentnost.
        _resumeMap = BuildResumeMap(config.SummaryCsvPath);
        _writer   = new ResultsWriter(config.ResultsCsvPath, config.SummaryCsvPath);
    }

    public async Task RunAllAsync(CancellationToken cancellationToken = default)
    {
        int completedRuns = 0;
        int runId = 1;

        // Resume logika: koristi _resumeMap pročitan u konstruktoru (PRIJE ResultsWriter).
        var resumeMap = _resumeMap;
        if (resumeMap.Count > 0)
            _logger.LogInformation("  Resume: pronađeno {N} kombinacija u postojećem CSV.", resumeMap.Count);

        _logger.LogInformation("Početak benchmarka. Ukupno kombinacija: {Total}", TotalRuns);
        _logger.LogInformation("Procijenjeno trajanje: {Hours:F1}h",
            TotalRuns * (_config.WarmupSeconds + _config.MeasurementSeconds) / 3600.0);

        foreach (var config in _config.Configurations)
        {
            string schema = config.ToLabel();
            // Oznaka ruke odvaja kontrolne runove (npr. "im@d2") od glavnog seta
            // u rezultatima i u resume logici; SQL i dalje cilja izvornu shemu.
            string armed = string.IsNullOrEmpty(_config.ArmLabel) ? schema : $"{schema}@{_config.ArmLabel}";
            _logger.LogInformation("=== Konfiguracija: {Config} ===", armed.ToUpper());

            WorkloadContext ctx;
            try
            {
                ctx = await _executor.LoadWorkloadContextAsync(schema);
                _logger.LogInformation(
                    "  Kontekst učitan: {Posts} postova, {Users} korisnika",
                    ctx.PostIds.Length, ctx.UserIds.Length);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "  GREŠKA pri učitavanju konteksta za {Config}. Preskačem.", schema);
                continue;
            }

            foreach (var ratio in _config.WorkloadRatios)
            {
                foreach (int concurrency in _config.ConcurrencyLevels)
                {
                    // Provjeri koliko runova postoji za ovu kombinaciju (resume podrška)
                    var comboKey = (armed, ratio.ToLabel(), concurrency);
                    int startRun = 1;
                    if (resumeMap.TryGetValue(comboKey, out int alreadyDone))
                    {
                        if (alreadyDone >= _config.RunsPerCombination)
                        {
                            _logger.LogInformation(
                                "  Preskačem {Ratio}/C={C} — već {N}/{Total} runova ✓",
                                ratio.ToLabel(), concurrency, alreadyDone, _config.RunsPerCombination);
                            runId += _config.RunsPerCombination;
                            completedRuns += _config.RunsPerCombination;
                            continue;
                        }
                        startRun = alreadyDone + 1;
                        runId += alreadyDone;
                        completedRuns += alreadyDone;
                        _logger.LogInformation(
                            "  Nastavljam od runa {Start} ({Ratio}/C={C})",
                            startRun, ratio.ToLabel(), concurrency);
                    }

                    // Pre-warm OLAP cache prije svake kombinacije da izbjegnemo cold-cache
                    // efekt koji uzrokuje 0 OLAP ops u prvim runovima.
                    try
                    {
                        await _executor.WarmOlapCacheAsync(schema);
                        _logger.LogInformation("  OLAP cache zagrijan.");
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "  OLAP cache warm-up nije uspio — nastavljam.");
                    }

                    _logger.LogInformation(
                        "  Ratio={Ratio}, Concurrency={C}, Runs={Start}-{N}",
                        ratio.ToLabel(), concurrency, startRun, _config.RunsPerCombination);

                    for (int run = startRun; run <= _config.RunsPerCombination; run++)
                    {
                        if (cancellationToken.IsCancellationRequested) return;

                        try
                        {
                            var outcome = await _executor.ExecuteRunAsync(
                                config, ratio, concurrency, run,
                                _config.WarmupSeconds, _config.MeasurementSeconds,
                                ctx, globalRunId: runId, cancellationToken);

                            var measurements = outcome.Measurements;
                            var summary = MetricsCalculator.Calculate(runId, measurements, _config.MeasurementSeconds);
                            summary.RunId = runId;
                            summary.ServerMetrics = outcome.ServerMetrics;
                            summary.Configuration = armed;

                            // Spremi sirova mjerenja i summary
                            foreach (var m in measurements)
                            {
                                m.RunId = runId;
                                m.Configuration = armed;
                            }

                            _writer.WriteMeasurements(measurements);
                            _writer.WriteSummary(summary);

                            completedRuns++;
                            runId++;

                            if (run % 5 == 0 || run == _config.RunsPerCombination)
                            {
                                _logger.LogInformation(
                                    "    Run {Run}/{Total}: OLTP={OltpTps:F0}ops/s P50={P50:F1}ms | " +
                                    "OLAP={OlapQps:F2}q/s P50={AP50:F0}ms | Progress={Pct:F1}%",
                                    run, _config.RunsPerCombination,
                                    summary.OltpThroughput, summary.OltpLatencyP50,
                                    summary.OlapThroughput, summary.OlapLatencyP50,
                                    completedRuns * 100.0 / TotalRuns);
                            }

                            // Cleanup nakon SVAKOG runa za IM/HTAP — drži RAM pod kontrolom.
                            // Proslijedi concurrency da GC intenzitet bude proporcionalan opterećenju.
                            if (schema is "im" or "htap" && run < _config.RunsPerCombination)
                            {
                                try { await _executor.CleanupBenchmarkDataAsync(schema, ctx, concurrency); }
                                catch (Exception ex)
                                {
                                    _logger.LogWarning(ex, "      [cleanup failed run {Run}]", run);
                                }

                                // Refresh aktivnih postova nakon svakog runa da spriječi nakupljanje
                                // MVCC version chains unutar kombinacije → OOM crash kod C=32.
                                // Briše i ponovo insertuje samo 20K aktivnih redova (ne svih 3.7M).
                                try { await _executor.TruncateAndReloadPostsAsync(schema, ctx.PostIds); }
                                catch (Exception ex)
                                {
                                    _logger.LogWarning(ex, "      [posts refresh failed run {Run}]", run);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex,
                                "    GREŠKA u runu {Config}/{Ratio}/{C}/#{Run}",
                                schema, ratio.ToLabel(), concurrency, run);
                        }
                    }

                    // Cleanup benchmark-insertovanih redova iz IM/HTAP tablica nakon svake kombinacije.
                    // Sprječava nekontrolirani rast in-memory tablica i OOM crash SQL Servera.
                    try
                    {
                        await _executor.CleanupBenchmarkDataAsync(schema, ctx, concurrency);
                        if (schema is "im" or "htap")
                            _logger.LogInformation("  Cleanup IM/HTAP redova završen ({Ratio}, C={C}).",
                                ratio.ToLabel(), concurrency);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "  Cleanup nije uspio ({Ratio}, C={C}) — nastavljam.", ratio.ToLabel(), concurrency);
                    }

                    // Resetiraj htap/im.Posts između kombinacija: refresh samo 20K aktivnih postova.
                    // UpdatePostScore akumulira MVCC version chains na Posts kroz sve runove kombinacije.
                    // Refresh SAMO aktivnih postova (ne svih 3.7M) → 185× manje GC rada.
                    if (schema is "im" or "htap")
                    {
                        try
                        {
                            await _executor.TruncateAndReloadPostsAsync(schema, ctx.PostIds);
                            _logger.LogInformation("  Posts refresh završen ({Ratio}, C={C}).",
                                ratio.ToLabel(), concurrency);
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning(ex, "  Posts reset nije uspio ({Ratio}, C={C}) — nastavljam.",
                                ratio.ToLabel(), concurrency);
                        }
                    }
                }
            }
        }

        _logger.LogInformation("Benchmark završen. Ukupno runova: {Completed}/{Total}", completedRuns, TotalRuns);
    }

    /// <summary>
    /// Čita postojeći summary CSV i vraća mapu (schema, ratio, concurrency) -> broj završenih runova.
    /// Koristi se za resume funkcionalnost — preskačemo kombinacije koje su već završene.
    /// Uzima se MAX(RunNumber) po kombinaciji (a ne COUNT) jer se run brojevi ne mijenjaju pri resume.
    /// </summary>
    private static Dictionary<(string, string, int), int> BuildResumeMap(string summaryPath)
    {
        var map = new Dictionary<(string, string, int), int>();
        if (string.IsNullOrEmpty(summaryPath) || !File.Exists(summaryPath))
            return map;

        try
        {
            foreach (var line in File.ReadLines(summaryPath).Skip(1)) // preskačemo header
            {
                var parts = line.Split(',');
                if (parts.Length < 4) continue;

                string schema      = parts[0].Trim();
                string ratioLabel  = parts[1].Trim();
                if (!int.TryParse(parts[2].Trim(), out int concurrency)) continue;
                if (!int.TryParse(parts[3].Trim(), out int runNumber))   continue;

                var key = (schema, ratioLabel, concurrency);
                if (!map.TryGetValue(key, out int existing) || runNumber > existing)
                    map[key] = runNumber;
            }
        }
        catch { /* Ignoriši greške parsiranja — krećemo od početka */ }

        return map;
    }

    public void Dispose() => _writer.Dispose();
}
