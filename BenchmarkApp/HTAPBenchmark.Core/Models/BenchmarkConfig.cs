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

    // =========================================================================
    // Instrumentacija i kontrolni eksperimenti
    // =========================================================================

    /// <summary>
    /// Oznaka eksperimenta koja se upisuje u sve izlazne datoteke. Odvaja glavni
    /// faktorijal od kontrolnih eksperimenata pri kasnijoj analizi.
    /// </summary>
    public string ExperimentTag { get; set; } = "main";

    /// <summary>
    /// Mjeri CPU potrošnju i raspodjelu čekanja po runu (sys.dm_os_schedulers,
    /// sys.dm_os_wait_stats). Pretpostavlja da je benchmark jedino opterećenje
    /// na instanci, jer su ti DMV-ovi instance-wide.
    /// </summary>
    public bool CollectResourceMetrics { get; set; }

    /// <summary>
    /// Varijante stepena paralelizma OLAP upita koje se mjere kao dodatna
    /// dimenzija eksperimenta. 0 = koristi originalne procedure (MAXDOP kakav
    /// je zatečen u shemi); 1 ili 2 = koristi _MD1 / _MD2 varijante iz
    /// 10_MaxDop_Control_Variants.sql.
    /// </summary>
    public int[] OlapMaxDopVariants { get; set; } = [0];

    /// <summary>
    /// Intervali sinhronizacije htap.* → cs.* (sekunde) koji se mjere kao dodatna
    /// dimenzija. 0 = bez sinhronizacije (kao u glavnom eksperimentu).
    /// Primjenjuje se isključivo na HTAP konfiguraciju.
    /// </summary>
    public int[] SyncIntervalsSeconds { get; set; } = [0];

    public string ResourceUsageCsvPath { get; set; } = "Results/resource_usage.csv";

    public string WaitStatsCsvPath { get; set; } = "Results/wait_stats.csv";

    public string SyncCyclesCsvPath { get; set; } = "Results/sync_cycles.csv";
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

    /// <summary>
    /// Oznaka koja se upisuje u summary.csv kao vrijednost kolone Configuration.
    /// Dimenzije kontrolnih eksperimenata kodiraju se u samu oznaku (npr.
    /// "htap_md1", "htap_sync5") umjesto kao dodatne kolone, čime shema
    /// summary.csv ostaje nepromijenjena — postojećih 1.070 mjerenja i analitičke
    /// skripte koje ih čitaju nastavljaju raditi bez izmjena, a resume logika
    /// ispravno razlikuje kombinacije različitih eksperimentalnih uvjeta.
    /// </summary>
    public static string ToRunLabel(this DbConfiguration config, int olapMaxDopVariant, int syncIntervalSeconds)
    {
        string label = config.ToLabel();
        if (olapMaxDopVariant is 1 or 2) label += $"_md{olapMaxDopVariant}";
        if (syncIntervalSeconds > 0)     label += $"_sync{syncIntervalSeconds}";
        return label;
    }
}
