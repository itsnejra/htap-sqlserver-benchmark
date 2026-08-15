namespace HTAPBenchmark.Core.Models;

/// <summary>Metrike jednog ciklusa sinhronizacije htap.* → cs.*.</summary>
public sealed class SyncCycleResult
{
    public int RunId { get; set; }
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
    /// Kašnjenje svježine (ms): vrijeme od nastanka reda u OLTP sloju do trenutka
    /// kad postaje vidljiv u analitičkom sloju. Mjereno nad propagiranim Comments
    /// redovima — jedini imaju punu vremensku oznaku (htap.Votes.CreationDate je
    /// tipa DATE). Rezolucija je 1 s jer je kolona DATETIME2(0).
    /// -1 = u ovom ciklusu nije bilo redova za mjerenje.
    /// </summary>
    public double AvgFreshnessLagMs { get; set; } = -1;
    public double MaxFreshnessLagMs { get; set; } = -1;

    public bool Success { get; set; } = true;
    public string? ErrorMessage { get; set; }
}
