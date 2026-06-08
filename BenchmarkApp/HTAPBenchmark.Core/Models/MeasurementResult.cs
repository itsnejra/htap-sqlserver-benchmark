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

    // Latencija percentili (ms)
    public double OltpLatencyP50 { get; set; }
    public double OltpLatencyP95 { get; set; }
    public double OltpLatencyP99 { get; set; }

    public double OlapLatencyP50 { get; set; }
    public double OlapLatencyP95 { get; set; }
    public double OlapLatencyP99 { get; set; }

    // Latencija statistike: min/avg/max/total (ms) — zahtjev predmeta
    public double OltpLatencyMin { get; set; }
    public double OltpLatencyAvg { get; set; }
    public double OltpLatencyMax { get; set; }
    public double OltpLatencyTotal { get; set; }

    public double OlapLatencyMin { get; set; }
    public double OlapLatencyAvg { get; set; }
    public double OlapLatencyMax { get; set; }
    public double OlapLatencyTotal { get; set; }

    // Iskorištenost resursa servera — SQL Server DMV snapshot kraj runa
    public double SqlCpuPercent { get; set; }
    public double SqlMemoryUsedMB { get; set; }

    public double OltpSuccessRate { get; set; }
    public double OlapSuccessRate { get; set; }

    public int OltpTotalOps { get; set; }
    public int OlapTotalOps { get; set; }
}

public class WorkloadContext
{
    public int[] PostIds { get; set; } = [];
    public int[] UserIds { get; set; } = [];
    public int NextVoteId { get; set; }
    public int NextCommentId { get; set; }
    public int OriginalMaxVoteId { get; set; }
    public int OriginalMaxCommentId { get; set; }

    /// <summary>
    /// Pool ID-ova glasanja koje je benchmark insertovao — koristi se za DELETE operacije.
    /// Worker niti enqueueuju ID nakon uspješnog InsertVote; DeleteVote dequeueuje.
    /// </summary>
    public System.Collections.Concurrent.ConcurrentQueue<int> AvailableVoteIdsForDelete { get; } = new();

    /// <summary>
    /// Pool ID-ova komentara koje je benchmark insertovao — za demonstraciju Complex DELETE.
    /// </summary>
    public System.Collections.Concurrent.ConcurrentQueue<int> AvailableCommentIdsForDelete { get; } = new();
}
