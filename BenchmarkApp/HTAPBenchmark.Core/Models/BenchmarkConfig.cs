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
    /// Sufiks imena OLAP pohranjenih procedura (npr. "_D2" → im.usp_OLAP_Q1_..._D2).
    /// Koristi se za MAXDOP kontrolni eksperiment (SQL/10_MaxDopControl.sql).
    /// Prazno = standardne procedure iz glavnog eksperimenta.
    /// </summary>
    public string OlapProcSuffix { get; set; } = string.Empty;

    /// <summary>
    /// Oznaka eksperimentalne ruke koja se dopisuje na Configuration u rezultatima
    /// (npr. "d2" → "im@d2"). Drži kontrolne runove odvojenima od glavnog seta
    /// u istom CSV-u i u resume logici.
    /// </summary>
    public string ArmLabel { get; set; } = string.Empty;

    /// <summary>Snimaj serverske brojače (CPU po tipu niti, wait statistika) oko mjerne faze.</summary>
    public bool CollectServerMetrics { get; set; } = true;

    /// <summary>
    /// Prije prvog runa provjeri da aktivna shema sadrži pun skup podataka i prekini
    /// ako ne sadrži. Štiti od mjerenja nad im.*/htap.* tablicama koje su se ispraznile
    /// pri restartu SQL Servera (DURABILITY = SCHEMA_ONLY). Isključuje se s --skip-verify.
    /// </summary>
    public bool VerifyDatasetBeforeRun { get; set; } = true;

    /// <summary>
    /// Interval periodične propagacije htap.* → cs.* u sekundama (0 = isključeno).
    /// Primjenjuje se samo na HTAP konfiguraciju. Mjerenjem pri više intervala
    /// dobiva se krivulja kompromisa između svježine analitičkih podataka i OLTP
    /// propusnosti. Preduvjet: SQL/11_DualStore_Sync.sql.
    /// </summary>
    public int SyncIntervalSeconds { get; set; }

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
}
