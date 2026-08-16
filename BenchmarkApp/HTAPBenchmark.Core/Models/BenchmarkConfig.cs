namespace HTAPBenchmark.Core.Models;

public enum DbConfiguration
{
    Baseline,
    CS,
    IM,
    HTAP
}

public enum WorkloadRatio
{
    OLTP80_OLAP20,
    OLTP50_OLAP50,
    OLTP20_OLAP80
}

public class BenchmarkConfig
{
    public string ConnectionString { get; set; } = string.Empty;

    public int WarmupSeconds { get; set; } = 10;

    public int MeasurementSeconds { get; set; } = 60;

    public int RunsPerCombination { get; set; } = 30;

    public int[] ConcurrencyLevels { get; set; } = [];

    public DbConfiguration[] Configurations { get; set; } = [];

    public WorkloadRatio[] WorkloadRatios { get; set; } = [];

    public string ResultsCsvPath { get; set; } = "Results/measurements.csv";

    public string SummaryCsvPath { get; set; } = "Results/summary.csv";

    /// <summary>
    /// Uključuje mjerenje resursa SQL Servera (wait statistike, runnable zadaci, CPU)
    /// tokom mjerne faze svakog runa. Zahtijeva VIEW SERVER STATE dozvolu.
    /// Isključeno po defaultu da ponašanje postojećih mjerenja ostane nepromijenjeno.
    /// </summary>
    public bool CollectResourceProfile { get; set; } = false;

    public string ResourcesCsvPath { get; set; } = "Results/resource_profile.csv";

    /// <summary>Interval uzorkovanja sys.dm_os_schedulers u milisekundama.</summary>
    public int ResourceSampleIntervalMs { get; set; } = 1000;

    /// <summary>
    /// Sufiks koji se dodaje imenima OLAP procedura, npr. "_Dop1" za izvođenje
    /// varijanti s OPTION (MAXDOP 1). Služi kontrolnom eksperimentu za H3: HTAP i IM
    /// se porede pri istom stepenu paralelizma, čime se uklanja confound iz glavnog
    /// mjerenja (MAXDOP 2 na HTAP naspram MAXDOP 1 na IM).
    /// Prazan string koristi originalne procedure.
    /// </summary>
    public string OlapProcedureSuffix { get; set; } = string.Empty;
}

public static class WorkloadRatioExtensions
{
    public static (double OltpFraction, double OlapFraction) GetFractions(this WorkloadRatio ratio) =>
        ratio switch
        {
            WorkloadRatio.OLTP80_OLAP20 => (0.80, 0.20),
            WorkloadRatio.OLTP50_OLAP50 => (0.50, 0.50),
            WorkloadRatio.OLTP20_OLAP80 => (0.20, 0.80),
            _ => throw new ArgumentOutOfRangeException(nameof(ratio))
        };

    public static string ToLabel(this WorkloadRatio ratio) =>
        ratio switch
        {
            WorkloadRatio.OLTP80_OLAP20 => "80_20",
            WorkloadRatio.OLTP50_OLAP50 => "50_50",
            WorkloadRatio.OLTP20_OLAP80 => "20_80",
            _ => throw new ArgumentOutOfRangeException(nameof(ratio))
        };

    public static string ToLabel(this DbConfiguration config) =>
        config switch
        {
            DbConfiguration.Baseline => "baseline",
            DbConfiguration.CS => "cs",
            DbConfiguration.IM => "im",
            DbConfiguration.HTAP => "htap",
            _ => throw new ArgumentOutOfRangeException(nameof(config))
        };
}
