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

// Provjeri command-line override-ove (za parcijalno pokretanje)
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
