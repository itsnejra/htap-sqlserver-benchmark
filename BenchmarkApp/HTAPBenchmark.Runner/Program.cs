using HTAPBenchmark.Core.Models;
using HTAPBenchmark.Core.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

// ============================================================
// HTAPBenchmark Runner
// Pokretanje: dotnet run --project HTAPBenchmark.Runner
// ili: dotnet run -- --config HTAP --ratio 80_20 --concurrency 16
// ============================================================

var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    Console.WriteLine("\nPrekid zahtjevan. Čekam na završetak trenutnog runa...");
    cts.Cancel();
};

var configuration = new ConfigurationBuilder()
    .SetBasePath(AppContext.BaseDirectory)
    .AddJsonFile("appsettings.json", optional: false)
    .AddEnvironmentVariables()   // npr. BenchmarkConfig__ConnectionString (Docker)
    .AddCommandLine(args)
    .Build();

var services = new ServiceCollection()
    .AddLogging(logging =>
    {
        logging.AddConsole(opts => opts.FormatterName = "simple");
        logging.SetMinimumLevel(LogLevel.Information);
    })
    .BuildServiceProvider();

var logger = services.GetRequiredService<ILogger<BenchmarkOrchestrator>>();

// Učitaj konfiguraciju (Get<> creates a fresh instance; Bind on pre-initialized obj doubles arrays)
var benchmarkConfig = configuration.GetSection("BenchmarkConfig").Get<BenchmarkConfig>()
    ?? new BenchmarkConfig();

// ============================================================
// Kontrolni eksperimenti (--experiment maxdop|sync|waits)
//
// Svaki preset piše u vlastite izlazne datoteke da ne bi pomiješao rezultate s
// glavnim faktorijalom u Results/summary.csv. Eksperimentalni uvjet se kodira u
// vrijednost kolone Configuration (npr. htap_md1, htap_sync5).
// ============================================================
var experimentArg = args.SkipWhile(a => a != "--experiment").Skip(1).FirstOrDefault();
if (experimentArg is not null)
{
    switch (experimentArg.ToLowerInvariant())
    {
        // MAXDOP kontrola: izolira confounding varijablu stepena paralelizma u
        // usporedbi HTAP naspram IM. Pun 2×2 faktorijal (konfiguracija × MAXDOP).
        // Preduvjet: SQL/10_MaxDop_Control_Variants.sql.
        case "maxdop":
            benchmarkConfig.ExperimentTag          = "maxdop_control";
            benchmarkConfig.Configurations         = [DbConfiguration.IM, DbConfiguration.HTAP];
            benchmarkConfig.WorkloadRatios         = [WorkloadRatio.OLTP80_OLAP20, WorkloadRatio.OLTP50_OLAP50];
            benchmarkConfig.ConcurrencyLevels      = [16, 32];
            benchmarkConfig.OlapMaxDopVariants     = [1, 2];
            benchmarkConfig.SyncIntervalsSeconds   = [0];
            benchmarkConfig.RunsPerCombination     = 10;
            benchmarkConfig.CollectResourceMetrics = true;
            benchmarkConfig.ResultsCsvPath         = "Results/maxdop_measurements.csv";
            benchmarkConfig.SummaryCsvPath         = "Results/maxdop_summary.csv";
            benchmarkConfig.ResourceUsageCsvPath   = "Results/maxdop_resource_usage.csv";
            benchmarkConfig.WaitStatsCsvPath       = "Results/maxdop_wait_stats.csv";
            logger.LogWarning("EKSPERIMENT: MAXDOP kontrola (IM/HTAP × MAXDOP 1/2, 2 omjera × 2 razine × 10 runova)");
            break;

        // Cijena sinhronizacije dual-store slojeva: OLTP propusnost i svježina
        // analitičkih podataka kao funkcija intervala propagacije.
        // Preduvjet: SQL/11_DualStore_Sync.sql.
        case "sync":
            benchmarkConfig.ExperimentTag          = "sync_cost";
            benchmarkConfig.Configurations         = [DbConfiguration.HTAP];
            benchmarkConfig.WorkloadRatios         = [WorkloadRatio.OLTP80_OLAP20, WorkloadRatio.OLTP50_OLAP50];
            benchmarkConfig.ConcurrencyLevels      = [16];
            benchmarkConfig.OlapMaxDopVariants     = [0];
            benchmarkConfig.SyncIntervalsSeconds   = [0, 1, 5, 30];
            benchmarkConfig.RunsPerCombination     = 10;
            benchmarkConfig.CollectResourceMetrics = true;
            benchmarkConfig.ResultsCsvPath         = "Results/sync_measurements.csv";
            benchmarkConfig.SummaryCsvPath         = "Results/sync_summary.csv";
            benchmarkConfig.ResourceUsageCsvPath   = "Results/sync_resource_usage.csv";
            benchmarkConfig.WaitStatsCsvPath       = "Results/sync_wait_stats.csv";
            benchmarkConfig.SyncCyclesCsvPath      = "Results/sync_cycles.csv";
            logger.LogWarning("EKSPERIMENT: cijena sinhronizacije (HTAP × interval 0/1/5/30 s, 2 omjera × 10 runova)");
            break;

        // Mjerenje CPU-a i čekanja nad podskupom glavnog dizajna. Daje direktan
        // dokaz za mehanizam CPU saturacije koji je u radu dosad bio samo izveden
        // iz modela izvršavanja upita.
        case "waits":
            benchmarkConfig.ExperimentTag          = "resource_profile";
            benchmarkConfig.Configurations         = [DbConfiguration.CS, DbConfiguration.IM, DbConfiguration.HTAP];
            benchmarkConfig.ConcurrencyLevels      = [4, 16, 32];
            benchmarkConfig.RunsPerCombination     = 10;
            benchmarkConfig.CollectResourceMetrics = true;
            benchmarkConfig.ResultsCsvPath         = "Results/profile_measurements.csv";
            benchmarkConfig.SummaryCsvPath         = "Results/profile_summary.csv";
            benchmarkConfig.ResourceUsageCsvPath   = "Results/profile_resource_usage.csv";
            benchmarkConfig.WaitStatsCsvPath       = "Results/profile_wait_stats.csv";
            logger.LogWarning("EKSPERIMENT: profil resursa (CS/IM/HTAP × 3 omjera × 3 razine × 10 runova)");
            break;

        default:
            logger.LogError("Nepoznat eksperiment '{Exp}'. Podržano: maxdop, sync, waits.", experimentArg);
            return;
    }
}

// Provjeri command-line override-ove (za parcijalno pokretanje).
// Namjerno DOLAZE POSLIJE preseta eksperimenata, da --quick i --dry-run mogu
// skratiti i kontrolne eksperimente pri provjeri postavke.
if (args.Contains("--quick"))
{
    benchmarkConfig.WarmupSeconds      = 5;
    benchmarkConfig.MeasurementSeconds = 30;
    benchmarkConfig.RunsPerCombination = 3;
    logger.LogWarning("QUICK MODE: warmup=5s, measurement=30s, runs=3");
}

if (args.Contains("--dry-run"))
{
    benchmarkConfig.WarmupSeconds      = 2;
    benchmarkConfig.MeasurementSeconds = 5;
    benchmarkConfig.RunsPerCombination = 1;
    logger.LogWarning("DRY RUN MODE: warmup=2s, measurement=5s, runs=1");
}

// Opcionalni filter po konfiguraciji (--only baseline,cs)
var onlyArg = args.SkipWhile(a => a != "--only").Skip(1).FirstOrDefault();
if (onlyArg is not null)
{
    var filter = onlyArg.Split(',', StringSplitOptions.RemoveEmptyEntries)
        .Select(s => Enum.Parse<DbConfiguration>(s, ignoreCase: true))
        .ToArray();
    benchmarkConfig.Configurations = filter;
    logger.LogInformation("Filter: samo konfiguracije {Configs}", string.Join(", ", filter));
}

logger.LogInformation("╔══════════════════════════════════════════════════════════╗");
logger.LogInformation("║   HTAPBenchmark - Evaluacija performansi HTAP paradigme  ║");
logger.LogInformation("╚══════════════════════════════════════════════════════════╝");
logger.LogInformation("Connection: {CS}", benchmarkConfig.ConnectionString[..Math.Min(60, benchmarkConfig.ConnectionString.Length)] + "...");
logger.LogInformation("Konfiguracije: {Configs}", string.Join(", ", benchmarkConfig.Configurations));
logger.LogInformation("Ratio-i:       {Ratios}", string.Join(", ", benchmarkConfig.WorkloadRatios));
logger.LogInformation("Concurrency:   {C}", string.Join(", ", benchmarkConfig.ConcurrencyLevels));
logger.LogInformation("Runs/combo:    {R}", benchmarkConfig.RunsPerCombination);
logger.LogInformation("Warmup:        {W}s | Measurement: {M}s", benchmarkConfig.WarmupSeconds, benchmarkConfig.MeasurementSeconds);
logger.LogInformation("Output:        {Path}", Path.GetFullPath(benchmarkConfig.ResultsCsvPath));

int totalRuns = benchmarkConfig.Configurations.Length *
                benchmarkConfig.WorkloadRatios.Length *
                benchmarkConfig.ConcurrencyLevels.Length *
                Math.Max(1, benchmarkConfig.OlapMaxDopVariants.Length) *
                Math.Max(1, benchmarkConfig.SyncIntervalsSeconds.Length) *
                benchmarkConfig.RunsPerCombination;

double estHours = totalRuns * (benchmarkConfig.WarmupSeconds + benchmarkConfig.MeasurementSeconds) / 3600.0;
logger.LogInformation("Ukupno runova: {Total} | Procjenjeno trajanje: {Hours:F1}h", totalRuns, estHours);
logger.LogInformation("");
logger.LogInformation("Pritisnite Ctrl+C za graceful prekid.");
logger.LogInformation("Pokretanje za 3 sekunde...");
await Task.Delay(3000, cts.Token).ContinueWith(_ => { });

if (cts.IsCancellationRequested)
{
    logger.LogInformation("Prekinuto.");
    return;
}

var orchestrator = new BenchmarkOrchestrator(benchmarkConfig, logger);

try
{
    var stopwatch = System.Diagnostics.Stopwatch.StartNew();
    await orchestrator.RunAllAsync(cts.Token);
    stopwatch.Stop();

    logger.LogInformation("");
    logger.LogInformation("╔══════════════════════════════════════════════════════════╗");
    logger.LogInformation("║                    BENCHMARK ZAVRŠEN                     ║");
    logger.LogInformation("╚══════════════════════════════════════════════════════════╝");
    logger.LogInformation("Ukupno trajanje:    {Time}", stopwatch.Elapsed.ToString(@"hh\:mm\:ss"));
    logger.LogInformation("Mjerenja CSV:       {Path}", Path.GetFullPath(benchmarkConfig.ResultsCsvPath));
    logger.LogInformation("Summary CSV:        {Path}", Path.GetFullPath(benchmarkConfig.SummaryCsvPath));
    logger.LogInformation("");
    logger.LogInformation("Sljedeći korak: pokrenite Analysis/02_statistical_tests.py");
}
catch (OperationCanceledException)
{
    logger.LogInformation("Benchmark prekinut od strane korisnika.");
}
catch (Exception ex)
{
    logger.LogCritical(ex, "Kritična greška u benchmarku.");
    throw;
}
finally
{
    orchestrator.Dispose();
}
