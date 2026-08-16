namespace HTAPBenchmark.Core.Models;

/// <summary>
/// Direktno izmjeren profil resursa SQL Servera tokom mjerne faze jednog runa.
///
/// Postoji da bi tvrdnja o CPU saturaciji (row-mode OLAP skenovi zasićuju procesor
/// u IM konfiguraciji) bila IZMJERENA, a ne izvedena iz modela izvršavanja upita.
/// Kombinuje dva komplementarna izvora:
///   1. delta sys.dm_os_wait_stats — koliko se čekalo i na šta;
///   2. periodično uzorkovanje sys.dm_os_schedulers i ring buffera — koliko je
///      zadataka bilo spremno za izvršavanje (runnable) i koliki je CPU procesa.
/// </summary>
public sealed class ResourceProfile
{
    public int RunId { get; set; }
    public string Configuration { get; set; } = string.Empty;
    public string OltpOlapRatio { get; set; } = string.Empty;
    public int ConcurrencyLevel { get; set; }
    public int RunNumber { get; set; }

    /// <summary>Broj uzoraka schedulera prikupljenih tokom mjerne faze.</summary>
    public int SampleCount { get; set; }

    /// <summary>
    /// Prosječan broj runnable zadataka po scheduleru. Zadatak u runnable redu ima
    /// sve što mu treba osim CPU-a, pa je ovo najdirektniji pokazatelj CPU pritiska:
    /// vrijednost &gt; 1 znači da niti čekaju na procesor.
    /// </summary>
    public double AvgRunnableTasksPerScheduler { get; set; }
    public double MaxRunnableTasksPerScheduler { get; set; }

    /// <summary>Prosječan broj aktivnih (radnih) zadataka po scheduleru.</summary>
    public double AvgActiveWorkersPerScheduler { get; set; }

    /// <summary>Prosječna iskorištenost CPU-a od strane SQL Server procesa (%).</summary>
    public double AvgSqlCpuPercent { get; set; }
    public double MaxSqlCpuPercent { get; set; }

    /// <summary>Prosječna ukupna iskorištenost CPU-a na mašini (%), uključujući ostale procese.</summary>
    public double AvgTotalCpuPercent { get; set; }

    /// <summary>
    /// Signal wait vrijeme kao udio ukupnog čekanja (%). Signal wait je vrijeme koje
    /// zadatak provede čekajući CPU nakon što je resurs koji je čekao postao dostupan;
    /// udio iznad ~25 % konvencionalno se tumači kao CPU pritisak.
    /// </summary>
    public double SignalWaitPercent { get; set; }

    public double TotalWaitTimeMs { get; set; }
    public double TotalSignalWaitTimeMs { get; set; }

    /// <summary>Delta po tipu čekanja tokom mjerne faze, sortirano po wait_time_ms.</summary>
    public List<WaitStatDelta> Waits { get; set; } = [];
}

/// <summary>Razlika sys.dm_os_wait_stats između kraja i početka mjerne faze.</summary>
public sealed class WaitStatDelta
{
    public string WaitType { get; set; } = string.Empty;
    public long WaitingTasksCount { get; set; }
    public double WaitTimeMs { get; set; }
    public double SignalWaitTimeMs { get; set; }
}
