namespace HTAPBenchmark.Core.Models;

public class MeasurementResult
{
    public int RunId { get; set; }
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }
    public string OperationType { get; set; } = string.Empty;  // OLTP | OLAP
    public string OperationName { get; set; } = string.Empty;
    public DateTime StartTimestamp { get; set; }
    public double LatencyMs { get; set; }
    public bool Success { get; set; } = true;
    public string? ErrorMessage { get; set; }
}

public class RunSummary
{
    public int RunId { get; set; }
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }

    public double OltpThroughput { get; set; }
    public double OlapThroughput { get; set; }

    public double OltpLatencyP50 { get; set; }
    public double OltpLatencyP95 { get; set; }
    public double OltpLatencyP99 { get; set; }

    public double OlapLatencyP50 { get; set; }
    public double OlapLatencyP95 { get; set; }
    public double OlapLatencyP99 { get; set; }

    public double OltpSuccessRate { get; set; }
    public double OlapSuccessRate { get; set; }

    public int OltpTotalOps { get; set; }
    public int OlapTotalOps { get; set; }

    /// <summary>Serverski brojači za ovaj run; null ako prikupljanje nije uključeno.</summary>
    public ServerMetrics? ServerMetrics { get; set; }
}

/// <summary>Rezultat jednog runa: sirova mjerenja klijenta + serverski brojači.</summary>
public sealed class RunOutcome
{
    public List<MeasurementResult> Measurements { get; set; } = [];
    public ServerMetrics? ServerMetrics { get; set; }

    /// <summary>Ciklusi sinhronizacije htap.* → cs.*; prazno kad sinhronizacija ne radi.</summary>
    public List<SyncCycleResult> SyncCycles { get; set; } = [];
}

public class WorkloadContext
{
    public int[] PostIds { get; set; } = [];
    public int[] UserIds { get; set; } = [];
    public int NextVoteId { get; set; }
    public int NextCommentId { get; set; }
    public int OriginalMaxVoteId { get; set; }
    public int OriginalMaxCommentId { get; set; }
}
