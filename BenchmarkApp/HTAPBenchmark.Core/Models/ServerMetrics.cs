namespace HTAPBenchmark.Core.Models;

/// <summary>
/// Sirovi snimak serverskih brojača uzet neposredno prije i neposredno poslije
/// mjerne faze runa. Razlika dva snimka daje <see cref="ServerMetrics"/>.
/// </summary>
public sealed class ServerSnapshot
{
    /// <summary>Kumulativno CPU vrijeme (ms) sesija označenih kao OLTP radne niti.</summary>
    public long OltpSessionCpuMs { get; set; }

    /// <summary>Kumulativno CPU vrijeme (ms) sesija označenih kao OLAP radne niti.</summary>
    public long OlapSessionCpuMs { get; set; }

    /// <summary>Kumulativno vrijeme čekanja (ms) po tipu čekanja, instanca-globalno.</summary>
    public Dictionary<string, long> WaitMs { get; set; } = new();

    /// <summary>Broj logičkih procesora vidljivih SQL Serveru.</summary>
    public int CpuCount { get; set; }
}

/// <summary>
/// Serverski izvedene metrike jednog runa, dobivene kao razlika dva
/// <see cref="ServerSnapshot"/>-a preko mjerne faze.
///
/// Svrha: direktno instrumentirati mehanizam CPU saturacije koji je u izvornom
/// radu bio samo IZVEDEN iz modela izvršavanja upita (row-mode vs batch-mode),
/// a ne mjeren. SOS_SCHEDULER_YIELD je direktni pokazatelj natjecanja za
/// procesorske resurse; podjela CPU vremena na OLTP i OLAP sesije pokazuje
/// KOLIKO procesora analitika oduzima transakcijskom sloju.
/// </summary>
public sealed class ServerMetrics
{
    public double OltpCpuMs { get; set; }
    public double OlapCpuMs { get; set; }

    public double TotalCpuMs => OltpCpuMs + OlapCpuMs;

    /// <summary>Udio ukupnog CPU vremena benchmarka potrošen na analitiku (0-1).</summary>
    public double OlapCpuShare => TotalCpuMs > 0 ? OlapCpuMs / TotalCpuMs : 0;

    /// <summary>
    /// Iskorištenost procesora benchmark sesijama:
    /// TotalCpuMs / (trajanje_mjerenja_ms * broj_jezgara) * 100.
    /// </summary>
    public double CpuUtilizationPct { get; set; }

    /// <summary>Čekanje na dodjelu kvantuma procesora — direktan indikator CPU pritiska.</summary>
    public double SchedulerYieldMs { get; set; }

    /// <summary>Sinhronizacija paralelnih grana plana (CXPACKET + CXCONSUMER).</summary>
    public double ParallelismWaitMs { get; set; }

    /// <summary>Sinhronizacija paralelnih planova nad Hekaton tabelama.</summary>
    public double CxSyncPortMs { get; set; }

    /// <summary>Čekanje na dodjelu memorijskog granta (batch-mode upiti).</summary>
    public double ResourceSemaphoreMs { get; set; }

    /// <summary>Čekanje na I/O čitanje stranice (disk-zasnovane konfiguracije).</summary>
    public double PageIoLatchMs { get; set; }

    /// <summary>Čekanje na upis u transakcijski log.</summary>
    public double WriteLogMs { get; set; }
}
