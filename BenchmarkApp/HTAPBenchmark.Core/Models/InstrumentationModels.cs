namespace HTAPBenchmark.Core.Models;

/// <summary>
/// Snapshot instance-wide brojača u jednom trenutku vremena.
/// Razlika dva snapshota daje potrošnju resursa unutar mjernog prozora.
/// </summary>
public sealed class ResourceSnapshot
{
    public DateTime TakenAtUtc { get; set; }

    /// <summary>Kumulativni CPU (ms) svih VISIBLE ONLINE schedulera — sys.dm_os_schedulers.total_cpu_usage_ms.</summary>
    public long SchedulerCpuMs { get; set; }

    /// <summary>Broj VISIBLE ONLINE schedulera (= broj logičkih jezgara dostupnih SQL Serveru).</summary>
    public int SchedulerCount { get; set; }

    /// <summary>Kumulativna čekanja po tipu — sys.dm_os_wait_stats.</summary>
    public Dictionary<string, WaitCounters> Waits { get; set; } = new();
}

public readonly record struct WaitCounters(long WaitTimeMs, long SignalWaitTimeMs, long WaitingTasksCount);

/// <summary>
/// Potrošnja resursa unutar jednog mjernog prozora (razlika dva snapshota).
/// </summary>
public sealed class ResourceUsage
{
    public int RunId { get; set; }
    public string ExperimentTag { get; set; } = "main";
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }
    public int OlapMaxDop { get; set; }
    public int SyncIntervalSeconds { get; set; }

    public double WindowMs { get; set; }
    public int SchedulerCount { get; set; }

    /// <summary>CPU vrijeme (ms) koje je SQL Server potrošio unutar prozora.</summary>
    public long SqlCpuMs { get; set; }

    /// <summary>
    /// Iskorištenost CPU kapaciteta dostupnog SQL Serveru:
    /// SqlCpuMs / (WindowMs × SchedulerCount) × 100.
    /// </summary>
    public double SqlCpuUtilPct =>
        WindowMs > 0 && SchedulerCount > 0
            ? SqlCpuMs / (WindowMs * SchedulerCount) * 100.0
            : 0.0;

    /// <summary>Ukupno vrijeme čekanja (ms) na sve ne-benigne tipove čekanja.</summary>
    public long TotalWaitMs { get; set; }

    /// <summary>
    /// Vrijeme provedeno u signal waitu (spremni za CPU, ali čekaju scheduler).
    /// Visok udio = CPU pritisak. Ovo je direktan pokazatelj CPU saturacije.
    /// </summary>
    public long TotalSignalWaitMs { get; set; }

    public double SignalWaitPct =>
        TotalWaitMs > 0 ? TotalSignalWaitMs * 100.0 / TotalWaitMs : 0.0;
}

/// <summary>Delta jednog tipa čekanja unutar mjernog prozora.</summary>
public sealed class WaitDelta
{
    public int RunId { get; set; }
    public string ExperimentTag { get; set; } = "main";
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }
    public int OlapMaxDop { get; set; }
    public int SyncIntervalSeconds { get; set; }

    public string WaitType { get; set; } = string.Empty;
    public long WaitTimeMs { get; set; }
    public long SignalWaitTimeMs { get; set; }
    public long WaitingTasksCount { get; set; }
}

/// <summary>Metrike jednog ciklusa sinhronizacije htap.* → cs.*.</summary>
public sealed class SyncCycleResult
{
    public int RunId { get; set; }
    public string ExperimentTag { get; set; } = "sync";
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }
    public int SyncIntervalSeconds { get; set; }

    public int CycleNumber { get; set; }
    public double DurationMs { get; set; }
    public int VotesPropagated { get; set; }
    public int CommentsPropagated { get; set; }
    public int PostsUpdated { get; set; }

    /// <summary>
    /// Prosječno kašnjenje svježine (ms): vrijeme od nastanka reda u OLTP sloju
    /// do trenutka kad postaje vidljiv u analitičkom sloju. Mjereno nad
    /// propagiranim Comments redovima (jedini imaju punu vremensku oznaku).
    /// -1 = nije bilo redova za mjerenje u ovom ciklusu.
    /// </summary>
    public double AvgFreshnessLagMs { get; set; } = -1;
    public double MaxFreshnessLagMs { get; set; } = -1;

    public bool Success { get; set; } = true;
    public string? ErrorMessage { get; set; }
}

/// <summary>Rezultat jednog mjernog runa: mjerenja + instrumentacija.</summary>
public sealed class RunOutcome
{
    public List<MeasurementResult> Measurements { get; set; } = [];
    public ResourceUsage? Resources { get; set; }
    public List<WaitDelta> Waits { get; set; } = [];
    public List<SyncCycleResult> SyncCycles { get; set; } = [];
}
