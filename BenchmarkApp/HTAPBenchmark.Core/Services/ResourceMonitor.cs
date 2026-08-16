using Dapper;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

/// <summary>
/// Mjeri iskorištenost resursa SQL Servera tokom mjerne faze jednog runa.
///
/// Radi na zasebnoj konekciji, paralelno s radnim nitima, i kombinuje:
///   • delta sys.dm_os_wait_stats između početka i kraja mjerne faze
///     (na šta se čekalo: CPU, memorijski grant, I/O, zaključavanje, paralelizam);
///   • uzorkovanje sys.dm_os_schedulers svakih SampleIntervalMs
///     (runnable_tasks_count > 1 po scheduleru = niti čekaju na procesor);
///   • deltu SUM(cpu_time) preko korisničkih sesija, normaliziranu brojem jezgara
///     (koliki je udio dostupnog CPU-a konfiguracija stvarno potrošila).
///
/// Zahtijeva VIEW SERVER STATE dozvolu. Ako je nema, monitor tiho vraća null i
/// benchmark se nastavlja bez profila resursa.
/// </summary>
public sealed class ResourceMonitor
{
    private readonly string _connectionString;
    private readonly int _sampleIntervalMs;

    public ResourceMonitor(string connectionString, int sampleIntervalMs = 1000)
    {
        _connectionString = connectionString;
        _sampleIntervalMs = Math.Max(100, sampleIntervalMs);
    }

    // Konvencionalna lista benignih tipova čekanja (idle/background) koji ne opisuju
    // opterećenje; isključuju se da CSV ostane čitljiv i da udjeli budu smisleni.
    private const string WaitStatsSql = @"
SELECT wait_type           AS WaitType,
       waiting_tasks_count AS WaitingTasksCount,
       wait_time_ms        AS WaitTimeMs,
       signal_wait_time_ms AS SignalWaitTimeMs
FROM sys.dm_os_wait_stats
WHERE wait_type NOT IN (
        N'BROKER_EVENTHANDLER', N'BROKER_RECEIVE_WAITFOR', N'BROKER_TASK_STOP',
        N'BROKER_TO_FLUSH', N'BROKER_TRANSMITTER', N'CHECKPOINT_QUEUE',
        N'CHKPT', N'CLR_AUTO_EVENT', N'CLR_MANUAL_EVENT', N'CLR_SEMAPHORE',
        N'DBMIRROR_DBM_EVENT', N'DBMIRROR_EVENTS_QUEUE', N'DBMIRROR_WORKER_QUEUE',
        N'DBMIRRORING_CMD', N'DIRTY_PAGE_POLL', N'DISPATCHER_QUEUE_SEMAPHORE',
        N'EXECSYNC', N'FSAGENT', N'FT_IFTS_SCHEDULER_IDLE_WAIT', N'FT_IFTSHC_MUTEX',
        N'HADR_CLUSAPI_CALL', N'HADR_FILESTREAM_IOMGR_IOCOMPLETION', N'HADR_LOGCAPTURE_WAIT',
        N'HADR_NOTIFICATION_DEQUEUE', N'HADR_TIMER_TASK', N'HADR_WORK_QUEUE',
        N'KSOURCE_WAKEUP', N'LAZYWRITER_SLEEP', N'LOGMGR_QUEUE', N'MEMORY_ALLOCATION_EXT',
        N'ONDEMAND_TASK_QUEUE', N'PARALLEL_REDO_DRAIN_WORKER', N'PARALLEL_REDO_LOG_CACHE',
        N'PARALLEL_REDO_TRAN_LIST', N'PARALLEL_REDO_WORKER_SYNC', N'PARALLEL_REDO_WORKER_WAIT_WORK',
        N'PREEMPTIVE_XE_GETTARGETSTATE', N'PWAIT_ALL_COMPONENTS_INITIALIZED',
        N'PWAIT_DIRECTLOGCONSUMER_GETNEXT', N'QDS_PERSIST_TASK_MAIN_LOOP_SLEEP',
        N'QDS_ASYNC_QUEUE', N'QDS_CLEANUP_STALE_QUERIES_TASK_MAIN_LOOP_SLEEP',
        N'QDS_SHUTDOWN_QUEUE', N'REDO_THREAD_PENDING_WORK', N'REQUEST_FOR_DEADLOCK_SEARCH',
        N'RESOURCE_QUEUE', N'SERVER_IDLE_CHECK', N'SLEEP_BPOOL_FLUSH', N'SLEEP_DBSTARTUP',
        N'SLEEP_DCOMSTARTUP', N'SLEEP_MASTERDBREADY', N'SLEEP_MASTERMDREADY',
        N'SLEEP_MASTERUPGRADED', N'SLEEP_MSDBSTARTUP', N'SLEEP_SYSTEMTASK', N'SLEEP_TASK',
        N'SLEEP_TEMPDBSTARTUP', N'SNI_HTTP_ACCEPT', N'SP_SERVER_DIAGNOSTICS_SLEEP',
        N'SQLTRACE_BUFFER_FLUSH', N'SQLTRACE_INCREMENTAL_FLUSH_SLEEP',
        N'SQLTRACE_WAIT_ENTRIES', N'WAIT_FOR_RESULTS', N'WAITFOR', N'WAITFOR_TASKSHUTDOWN',
        N'WAIT_XTP_RECOVERY', N'WAIT_XTP_HOST_WAIT', N'WAIT_XTP_OFFLINE_CKPT_NEW_LOG',
        N'WAIT_XTP_CKPT_CLOSE', N'XE_DISPATCHER_JOIN', N'XE_DISPATCHER_WAIT',
        N'XE_TIMER_EVENT', N'XE_LIVE_TARGET_TVF')
  AND waiting_tasks_count > 0;";

    private const string SchedulerSampleSql = @"
SELECT COUNT(*)                                    AS Schedulers,
       SUM(CAST(runnable_tasks_count AS float))    AS Runnable,
       SUM(CAST(active_workers_count AS float))    AS ActiveWorkers
FROM sys.dm_os_schedulers
WHERE status = N'VISIBLE ONLINE';";

    private const string SessionCpuSql = @"
SELECT ISNULL(SUM(CAST(cpu_time AS bigint)), 0)
FROM sys.dm_exec_sessions
WHERE is_user_process = 1;";

    // Ring buffer se osvježava jednom u minuti, pa unutar runa od 60 s daje 1-2 različite
    // vrijednosti. Služi kao gruba provjera opterećenja cijele mašine, ne kao primarna mjera.
    private const string MachineCpuSql = @"
SELECT TOP 1
       t.r.value('(//SystemHealth/ProcessUtilization)[1]', 'int') AS SqlCpu,
       100 - t.r.value('(//SystemHealth/SystemIdle)[1]', 'int')   AS TotalCpu
FROM (SELECT CONVERT(xml, record) AS r, [timestamp]
      FROM sys.dm_os_ring_buffers
      WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
        AND record LIKE N'%<SystemHealth>%') AS t
ORDER BY t.[timestamp] DESC;";

    /// <summary>
    /// Prati mjernu fazu jednog runa. Poziva se paralelno s
    /// <see cref="WorkloadExecutor.ExecuteRunAsync"/>: prvo prespava warmup fazu,
    /// zatim uzorkuje kroz mjernu fazu i vraća profil.
    /// Vraća null ako DMV-i nisu dostupni (nedostatak VIEW SERVER STATE dozvole).
    /// </summary>
    public async Task<ResourceProfile?> ProfileRunAsync(
        DbConfiguration config,
        WorkloadRatio ratio,
        int concurrencyLevel,
        int runNumber,
        int warmupSeconds,
        int measurementSeconds,
        CancellationToken ct = default)
    {
        try
        {
            await using var conn = new SqlConnection(_connectionString);
            await conn.OpenAsync(ct);

            int cpuCount = await conn.ExecuteScalarAsync<int>("SELECT cpu_count FROM sys.dm_os_sys_info;");
            if (cpuCount <= 0) cpuCount = Environment.ProcessorCount;

            // Warmup faza se ne mjeri — čekamo da radne niti uđu u mjernu fazu.
            await Task.Delay(TimeSpan.FromSeconds(warmupSeconds), ct);

            var waitsBefore = await ReadWaitStatsAsync(conn);
            long cpuMsBefore = await conn.ExecuteScalarAsync<long>(SessionCpuSql);
            var startedAt = DateTime.UtcNow;
            var endsAt = startedAt.AddSeconds(measurementSeconds);

            double runnableSum = 0, runnableMax = 0, activeSum = 0;
            double sqlCpuMax = 0, totalCpuSum = 0;
            int samples = 0, cpuSamples = 0;

            while (DateTime.UtcNow < endsAt && !ct.IsCancellationRequested)
            {
                try
                {
                    var s = await conn.QuerySingleAsync<SchedulerSample>(SchedulerSampleSql);
                    if (s.Schedulers > 0)
                    {
                        double runnablePerScheduler = s.Runnable / s.Schedulers;
                        runnableSum += runnablePerScheduler;
                        activeSum += s.ActiveWorkers / s.Schedulers;
                        if (runnablePerScheduler > runnableMax) runnableMax = runnablePerScheduler;
                        samples++;
                    }

                    var cpu = await conn.QuerySingleOrDefaultAsync<MachineCpuSample>(MachineCpuSql);
                    if (cpu is not null)
                    {
                        totalCpuSum += cpu.TotalCpu;
                        if (cpu.SqlCpu > sqlCpuMax) sqlCpuMax = cpu.SqlCpu;
                        cpuSamples++;
                    }
                }
                catch
                {
                    // Pojedinačni neuspjeli uzorak ne prekida profiliranje.
                }

                var remaining = endsAt - DateTime.UtcNow;
                if (remaining <= TimeSpan.Zero) break;
                await Task.Delay(remaining < TimeSpan.FromMilliseconds(_sampleIntervalMs)
                    ? remaining
                    : TimeSpan.FromMilliseconds(_sampleIntervalMs), ct);
            }

            var waitsAfter = await ReadWaitStatsAsync(conn);
            long cpuMsAfter = await conn.ExecuteScalarAsync<long>(SessionCpuSql);
            double elapsedMs = (DateTime.UtcNow - startedAt).TotalMilliseconds;

            var deltas = DiffWaitStats(waitsBefore, waitsAfter);
            double totalWait = deltas.Sum(d => d.WaitTimeMs);
            double totalSignal = deltas.Sum(d => d.SignalWaitTimeMs);

            // Udio dostupnog CPU kapaciteta (svih jezgara) potrošen na korisničke sesije.
            double sessionCpuPercent = elapsedMs > 0
                ? (cpuMsAfter - cpuMsBefore) / (elapsedMs * cpuCount) * 100.0
                : 0;

            return new ResourceProfile
            {
                Configuration    = config.ToLabel(),
                OltpOlapRatio    = ratio.ToLabel(),
                ConcurrencyLevel = concurrencyLevel,
                RunNumber        = runNumber,
                SampleCount      = samples,
                AvgRunnableTasksPerScheduler = samples > 0 ? runnableSum / samples : 0,
                MaxRunnableTasksPerScheduler = runnableMax,
                AvgActiveWorkersPerScheduler = samples > 0 ? activeSum / samples : 0,
                // Delta cpu_time je precizniji od ring buffera (koji se osvježava jednom u minuti),
                // pa se koristi kao primarna mjera; ring buffer ostaje kao provjera na razini mašine.
                AvgSqlCpuPercent   = sessionCpuPercent,
                MaxSqlCpuPercent   = cpuSamples > 0 ? sqlCpuMax : 0,
                AvgTotalCpuPercent = cpuSamples > 0 ? totalCpuSum / cpuSamples : 0,
                SignalWaitPercent  = totalWait > 0 ? totalSignal / totalWait * 100.0 : 0,
                TotalWaitTimeMs    = totalWait,
                TotalSignalWaitTimeMs = totalSignal,
                Waits = deltas
            };
        }
        catch (OperationCanceledException)
        {
            return null;
        }
        catch
        {
            // Najčešći uzrok: nedostatak VIEW SERVER STATE dozvole. Benchmark se nastavlja.
            return null;
        }
    }

    private static async Task<Dictionary<string, WaitStatDelta>> ReadWaitStatsAsync(SqlConnection conn)
    {
        var rows = await conn.QueryAsync<WaitStatDelta>(WaitStatsSql);
        return rows.ToDictionary(r => r.WaitType, StringComparer.Ordinal);
    }

    private static List<WaitStatDelta> DiffWaitStats(
        Dictionary<string, WaitStatDelta> before,
        Dictionary<string, WaitStatDelta> after)
    {
        var result = new List<WaitStatDelta>();

        foreach (var (waitType, end) in after)
        {
            before.TryGetValue(waitType, out var start);

            double waitMs   = end.WaitTimeMs       - (start?.WaitTimeMs       ?? 0);
            double signalMs = end.SignalWaitTimeMs - (start?.SignalWaitTimeMs ?? 0);
            long tasks      = end.WaitingTasksCount - (start?.WaitingTasksCount ?? 0);

            // Negativne delte znače da je statistika u međuvremenu resetirana — preskačemo.
            if (waitMs <= 0 && tasks <= 0) continue;

            result.Add(new WaitStatDelta
            {
                WaitType          = waitType,
                WaitingTasksCount = Math.Max(0, tasks),
                WaitTimeMs        = Math.Max(0, waitMs),
                SignalWaitTimeMs  = Math.Max(0, signalMs)
            });
        }

        return result.OrderByDescending(r => r.WaitTimeMs).ToList();
    }

    public sealed class SchedulerSample
    {
        public double Schedulers { get; set; }
        public double Runnable { get; set; }
        public double ActiveWorkers { get; set; }
    }

    public sealed class MachineCpuSample
    {
        public int SqlCpu { get; set; }
        public int TotalCpu { get; set; }
    }
}
