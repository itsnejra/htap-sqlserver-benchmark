using Dapper;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

/// <summary>
/// Prikuplja serverske brojače (CPU po tipu radne niti + wait statistiku) oko
/// mjerne faze runa.
///
/// CPU se atribuira preko <c>sys.dm_exec_sessions.cpu_time</c>, a radne niti se
/// razlikuju po <c>Application Name</c> u connection stringu
/// (<see cref="OltpAppName"/> / <see cref="OlapAppName"/>). Ovaj pristup je
/// odabran umjesto <c>sys.dm_exec_procedure_stats</c> jer nativno kompajlirane
/// procedure (IM, HTAP) ne prijavljuju statistiku izvršavanja bez
/// <c>sys.sp_xtp_control_proc_exec_stats</c>, čije bi uključivanje unijelo
/// overhead upravo u OLTP putanju koju mjerimo.
///
/// Snimanje se izvodi na zasebnoj vezi (Application Name = HTAPBench-Monitor),
/// koja je isključena iz agregacije, i traje red veličine jedne milisekunde,
/// pa ne perturbira mjerenje.
/// </summary>
public sealed class ServerMetricsCollector
{
    public const string OltpAppName    = "HTAPBench-OLTP";
    public const string OlapAppName    = "HTAPBench-OLAP";
    public const string MonitorAppName = "HTAPBench-Monitor";

    /// <summary>Tipovi čekanja koji nose interpretaciju u analizi interference.</summary>
    private static readonly string[] TrackedWaits =
    [
        "SOS_SCHEDULER_YIELD",
        "CXPACKET",
        "CXCONSUMER",
        "CXSYNC_PORT",
        "RESOURCE_SEMAPHORE",
        "RESOURCE_SEMAPHORE_QUERY_COMPILE",
        "PAGEIOLATCH_SH",
        "PAGEIOLATCH_EX",
        "WRITELOG"
    ];

    private readonly string _monitorConnectionString;

    public ServerMetricsCollector(string baseConnectionString)
    {
        _monitorConnectionString = new SqlConnectionStringBuilder(baseConnectionString)
        {
            ApplicationName = MonitorAppName
        }.ConnectionString;
    }

    /// <summary>Označi connection string imenom aplikacije da bi se CPU mogao atribuirati.</summary>
    public static string Tag(string connectionString, string appName) =>
        new SqlConnectionStringBuilder(connectionString) { ApplicationName = appName }.ConnectionString;

    public async Task<ServerSnapshot> SnapshotAsync(CancellationToken ct = default)
    {
        await using var conn = new SqlConnection(_monitorConnectionString);
        await conn.OpenAsync(ct);

        var snapshot = new ServerSnapshot();

        snapshot.CpuCount = await conn.ExecuteScalarAsync<int>(
            new CommandDefinition("SELECT cpu_count FROM sys.dm_os_sys_info;",
                commandTimeout: 30, cancellationToken: ct));

        // cpu_time je kumulativan po sesiji; radne niti žive kroz cijeli run,
        // pa je razlika dva snimka CPU utrošen unutar mjerne faze.
        const string cpuSql = """
            SELECT program_name AS AppName,
                   SUM(CAST(cpu_time AS BIGINT)) AS CpuMs
            FROM sys.dm_exec_sessions
            WHERE program_name IN (@Oltp, @Olap)
            GROUP BY program_name;
            """;

        var cpuRows = await conn.QueryAsync<CpuRow>(
            new CommandDefinition(cpuSql, new { Oltp = OltpAppName, Olap = OlapAppName },
                commandTimeout: 30, cancellationToken: ct));

        foreach (var row in cpuRows)
        {
            if (row.AppName == OltpAppName) snapshot.OltpSessionCpuMs = row.CpuMs;
            else if (row.AppName == OlapAppName) snapshot.OlapSessionCpuMs = row.CpuMs;
        }

        const string waitSql = """
            SELECT wait_type AS WaitType, wait_time_ms AS WaitMs
            FROM sys.dm_os_wait_stats
            WHERE wait_type IN @Waits;
            """;

        var waitRows = await conn.QueryAsync<WaitRow>(
            new CommandDefinition(waitSql, new { Waits = TrackedWaits },
                commandTimeout: 30, cancellationToken: ct));

        foreach (var row in waitRows)
            snapshot.WaitMs[row.WaitType] = row.WaitMs;

        return snapshot;
    }

    /// <summary>
    /// Razlika dva snimka. Negativne razlike (moguće ako se sesija zatvorila ili
    /// je DBCC SQLPERF resetirao brojače) svode se na nulu.
    /// </summary>
    public static ServerMetrics Delta(ServerSnapshot before, ServerSnapshot after, int measurementSeconds)
    {
        static double Diff(long b, long a) => Math.Max(0, a - b);

        double WaitDiff(params string[] types) => types.Sum(t =>
            Diff(before.WaitMs.GetValueOrDefault(t), after.WaitMs.GetValueOrDefault(t)));

        var metrics = new ServerMetrics
        {
            OltpCpuMs           = Diff(before.OltpSessionCpuMs, after.OltpSessionCpuMs),
            OlapCpuMs           = Diff(before.OlapSessionCpuMs, after.OlapSessionCpuMs),
            SchedulerYieldMs    = WaitDiff("SOS_SCHEDULER_YIELD"),
            ParallelismWaitMs   = WaitDiff("CXPACKET", "CXCONSUMER"),
            CxSyncPortMs        = WaitDiff("CXSYNC_PORT"),
            ResourceSemaphoreMs = WaitDiff("RESOURCE_SEMAPHORE", "RESOURCE_SEMAPHORE_QUERY_COMPILE"),
            PageIoLatchMs       = WaitDiff("PAGEIOLATCH_SH", "PAGEIOLATCH_EX"),
            WriteLogMs          = WaitDiff("WRITELOG")
        };

        int cores = Math.Max(1, after.CpuCount);
        double capacityMs = measurementSeconds * 1000.0 * cores;
        metrics.CpuUtilizationPct = capacityMs > 0 ? metrics.TotalCpuMs / capacityMs * 100.0 : 0;

        return metrics;
    }

    // Dapper ne mapira ValueTuple na kolone rezultata — potrebni su imenovani tipovi.
    private sealed class CpuRow
    {
        public string AppName { get; set; } = string.Empty;
        public long CpuMs { get; set; }
    }

    private sealed class WaitRow
    {
        public string WaitType { get; set; } = string.Empty;
        public long WaitMs { get; set; }
    }
}
