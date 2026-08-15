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

    // Ukupan broj kombinacija: config × ratio × concurrency × runs,
    // pomnoženo dimenzijama kontrolnih eksperimenata (MAXDOP varijante, sync intervali).
    // U glavnom eksperimentu obje dodatne dimenzije imaju po jedan element, pa je
    // ukupan broj kao i prije: 4 × 3 × 3 × 30 = 1080.
    public int TotalRuns =>
        _config.Configurations.Length *
        _config.WorkloadRatios.Length *
        _config.ConcurrencyLevels.Length *
        Math.Max(1, _config.OlapMaxDopVariants.Length) *
        Math.Max(1, _config.SyncIntervalsSeconds.Length) *
        _config.RunsPerCombination;

    public BenchmarkOrchestrator(
        BenchmarkConfig config,
        ILogger<BenchmarkOrchestrator> logger)
    {
        _config   = config;
        _executor = new WorkloadExecutor(config.ConnectionString, config.CollectResourceMetrics);
        _logger   = logger;
        // VAŽNO: pročitaj resume stanje PRIJE nego ResultsWriter otvori fajlove.
        // ResultsWriter koristi append:true ali drži file handle koji može spriječiti
        // konkurentno čitanje u nekim scenarijima. Čitanjem prvo garantiramo konzistentnost.
        _resumeMap = BuildResumeMap(config.SummaryCsvPath);
        _writer   = new ResultsWriter(
            config.ResultsCsvPath,
            config.SummaryCsvPath,
            config.CollectResourceMetrics ? config.ResourceUsageCsvPath : null,
            config.CollectResourceMetrics ? config.WaitStatsCsvPath : null,
            config.SyncIntervalsSeconds.Any(s => s > 0) ? config.SyncCyclesCsvPath : null);
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
            _logger.LogInformation("=== Konfiguracija: {Config} ===", schema.ToUpper());

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

            // Eksplicitni tip: collection expression [0] nema ciljni tip u `var` deklaraciji.
            int[] maxDopVariants = _config.OlapMaxDopVariants.Length > 0 ? _config.OlapMaxDopVariants : [0];
            int[] syncIntervals  = _config.SyncIntervalsSeconds.Length > 0 ? _config.SyncIntervalsSeconds : [0];

            // Sinhronizacija se odnosi isključivo na HTAP dual-store konfiguraciju;
            // ostale konfiguracije nemaju odvojen analitički sloj koji bi se punio.
            if (config != DbConfiguration.HTAP && syncIntervals.Any(s => s > 0))
            {
                syncIntervals = [0];
                _logger.LogInformation("  Sync intervali se preskaču za {Config} (nema dual-store sloja).", schema);
            }

            if (config == DbConfiguration.HTAP && syncIntervals.Any(s => s > 0))
            {
                try
                {
                    await DualStoreSynchronizer.PrepareAsync(_config.ConnectionString, ctx.PostIds, cancellationToken);
                    _logger.LogInformation("  Sync baseline snimljen ({N} aktivnih postova).", ctx.PostIds.Length);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "  GREŠKA pri pripremi sinhronizacije. Preskačem {Config}.", schema);
                    continue;
                }
            }

            foreach (int olapMaxDop in maxDopVariants)
            foreach (int syncInterval in syncIntervals)
            {
            string runLabel = config.ToRunLabel(olapMaxDop, syncInterval);
            if (runLabel != schema)
                _logger.LogInformation("--- Uvjet: {Label} (MAXDOP={Dop}, sync={Sync}s) ---",
                    runLabel, olapMaxDop == 0 ? "originalni" : olapMaxDop.ToString(), syncInterval);

            foreach (var ratio in _config.WorkloadRatios)
            {
                foreach (int concurrency in _config.ConcurrencyLevels)
                {
                    // Provjeri koliko runova postoji za ovu kombinaciju (resume podrška)
                    var comboKey = (runLabel, ratio.ToLabel(), concurrency);
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
                        await _executor.WarmOlapCacheAsync(schema, olapMaxDop);
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
                                ctx, globalRunId: runId,
                                olapMaxDopVariant: olapMaxDop,
                                syncIntervalSeconds: syncInterval,
                                cancellationToken: cancellationToken);

                            var measurements = outcome.Measurements;

                            var summary = MetricsCalculator.Calculate(runId, measurements, _config.MeasurementSeconds);
                            summary.RunId = runId;
                            // Eksperimentalni uvjet se kodira u oznaku konfiguracije
                            // (npr. htap_md1), da resume logika i analiza razlikuju uvjete.
                            summary.Configuration = runLabel;

                            // Spremi sirova mjerenja i summary
                            foreach (var m in measurements)
                            {
                                m.RunId = runId;
                                m.Configuration = runLabel;
                            }

                            _writer.WriteMeasurements(measurements);
                            _writer.WriteSummary(summary);

                            if (outcome.Resources is not null)
                            {
                                Annotate(outcome.Resources, runId, runLabel, ratio, concurrency, run, olapMaxDop, syncInterval);
                                _writer.WriteResourceUsage(outcome.Resources);
                            }

                            if (outcome.Waits.Count > 0)
                            {
                                foreach (var w in outcome.Waits)
                                    Annotate(w, runId, runLabel, ratio, concurrency, run, olapMaxDop, syncInterval);
                                _writer.WriteWaits(outcome.Waits);
                            }

                            if (outcome.SyncCycles.Count > 0)
                            {
                                foreach (var c in outcome.SyncCycles)
                                {
                                    c.RunId               = runId;
                                    c.ExperimentTag       = _config.ExperimentTag;
                                    c.Configuration       = runLabel;
                                    c.OltpOlapRatio       = ratio.ToLabel();
                                    c.ConcurrencyLevel    = concurrency;
                                    c.RunNumber           = run;
                                    c.SyncIntervalSeconds = syncInterval;
                                }
                                _writer.WriteSyncCycles(outcome.SyncCycles);
                            }

                            // Vrati cs.* sloj u polazno stanje: sinhronizacija je u njega
                            // upisala redove i izmijenila Score vrijednosti, a sljedeći run
                            // mora krenuti iz identičnog stanja podataka.
                            if (syncInterval > 0)
                            {
                                try
                                {
                                    await DualStoreSynchronizer.CleanupAsync(
                                        _config.ConnectionString, ctx, cancellationToken);
                                }
                                catch (Exception ex)
                                {
                                    _logger.LogWarning(ex, "      [sync cleanup failed run {Run}]", run);
                                }
                            }

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
                                runLabel, ratio.ToLabel(), concurrency, run);
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
            } // kraj petlji po MAXDOP varijantama i sync intervalima
        }

        _logger.LogInformation("Benchmark završen. Ukupno runova: {Completed}/{Total}", completedRuns, TotalRuns);
    }

    /// <summary>
    /// Popunjava identifikacijska polja instrumentacijskih zapisa. ResourceMonitor i
    /// DualStoreSynchronizer mjere resurse i ne poznaju eksperimentalni kontekst, pa
    /// im ga orkestrator pridružuje na jednom mjestu.
    /// </summary>
    private void Annotate(
        ResourceUsage usage, int runId, string runLabel, WorkloadRatio ratio,
        int concurrency, int run, int olapMaxDop, int syncInterval)
    {
        usage.RunId               = runId;
        usage.ExperimentTag       = _config.ExperimentTag;
        usage.Configuration       = runLabel;
        usage.OltpOlapRatio       = ratio.ToLabel();
        usage.ConcurrencyLevel    = concurrency;
        usage.RunNumber           = run;
        usage.OlapMaxDop          = olapMaxDop;
        usage.SyncIntervalSeconds = syncInterval;
    }

    private void Annotate(
        WaitDelta wait, int runId, string runLabel, WorkloadRatio ratio,
        int concurrency, int run, int olapMaxDop, int syncInterval)
    {
        wait.RunId               = runId;
        wait.ExperimentTag       = _config.ExperimentTag;
        wait.Configuration       = runLabel;
        wait.OltpOlapRatio       = ratio.ToLabel();
        wait.ConcurrencyLevel    = concurrency;
        wait.RunNumber           = run;
        wait.OlapMaxDop          = olapMaxDop;
        wait.SyncIntervalSeconds = syncInterval;
    }

    /// <summary>
    /// Čita postojeći summary CSV i vraća mapu (runLabel, ratio, concurrency) -> broj završenih runova.
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
