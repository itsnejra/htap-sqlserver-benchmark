using Dapper;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

/// <summary>
/// Mjeri stvarnu potrošnju CPU-a i raspodjelu čekanja unutar mjernog prozora.
///
/// MOTIVACIJA: interpretacija rezultata benchmarka počiva na tvrdnji da row-mode
/// OLAP skeniranja u IM konfiguraciji zasićuju procesor i time istiskuju OLTP niti.
/// Bez ove instrumentacije ta tvrdnja je izvedena iz modela izvršavanja upita, a ne
/// izmjerena. Klasa uzima snapshot instance-wide brojača na početku i kraju mjerne
/// faze; razlika daje CPU vrijeme i čekanja koja pripadaju isključivo tom prozoru.
///
/// OGRANIČENJE: sys.dm_os_wait_stats i sys.dm_os_schedulers su instance-wide, pa
/// mjerenje pretpostavlja da je benchmark jedino opterećenje na instanci. Isto
/// ograničenje vrijedi za svaki alat koji koristi ove DMV-ove.
/// </summary>
public sealed class ResourceMonitor
{
    private readonly string _connectionString;

    /// <summary>
    /// Broj tipova čekanja koji se zadržavaju po runu (sortirano po WaitTimeMs).
    /// Rep distribucije čekanja je dug i beznačajan; 15 pokriva >99% ukupnog vremena.
    /// </summary>
    public const int TopWaitsPerRun = 15;

    public ResourceMonitor(string connectionString)
    {
        _connectionString = connectionString;
    }

    /// <summary>
    /// Benigna čekanja koja ne predstavljaju kontenciju za resursima:
    /// pozadinske niti koje spavaju, brokeri, čekanje na red poslova.
    /// Standardni filter koji koriste i Microsoftove smjernice za analizu čekanja.
    /// </summary>
    private const string BenignWaitFilter = """
        wait_type NOT IN (
            'BROKER_EVENTHANDLER','BROKER_RECEIVE_WAITFOR','BROKER_TASK_STOP',
            'BROKER_TO_FLUSH','BROKER_TRANSMITTER','CHECKPOINT_QUEUE',
            'CHKPT','CLR_AUTO_EVENT','CLR_MANUAL_EVENT','CLR_SEMAPHORE',
            'DBMIRROR_DBM_EVENT','DBMIRROR_EVENTS_QUEUE','DBMIRROR_WORKER_QUEUE',
            'DBMIRRORING_CMD','DIRTY_PAGE_POLL','DISPATCHER_QUEUE_SEMAPHORE',
            'EXECSYNC','FSAGENT','FT_IFTS_SCHEDULER_IDLE_WAIT','FT_IFTSHC_MUTEX',
            'HADR_CLUSAPI_CALL','HADR_FILESTREAM_IOMGR_IOCOMPLETION','HADR_LOGCAPTURE_WAIT',
            'HADR_NOTIFICATION_DEQUEUE','HADR_TIMER_TASK','HADR_WORK_QUEUE',
            'KSOURCE_WAKEUP','LAZYWRITER_SLEEP','LOGMGR_QUEUE','MEMORY_ALLOCATION_EXT',
            'ONDEMAND_TASK_QUEUE','PARALLEL_REDO_DRAIN_WORKER','PARALLEL_REDO_LOG_CACHE',
            'PARALLEL_REDO_TRAN_LIST','PARALLEL_REDO_WORKER_SYNC','PARALLEL_REDO_WORKER_WAIT_WORK',
            'PREEMPTIVE_XE_GETTARGETSTATE','PWAIT_ALL_COMPONENTS_INITIALIZED',
            'PWAIT_DIRECTLOGCONSUMER_GETNEXT','QDS_PERSIST_TASK_MAIN_LOOP_SLEEP',
            'QDS_ASYNC_QUEUE','QDS_CLEANUP_STALE_QUERIES_TASK_MAIN_LOOP_SLEEP',
            'QDS_SHUTDOWN_QUEUE','REDO_THREAD_PENDING_WORK','REQUEST_FOR_DEADLOCK_SEARCH',
            'RESOURCE_QUEUE','SERVER_IDLE_CHECK','SLEEP_BPOOL_FLUSH','SLEEP_DBSTARTUP',
            'SLEEP_DCOMSTARTUP','SLEEP_MASTERDBREADY','SLEEP_MASTERMDREADY',
            'SLEEP_MASTERUPGRADED','SLEEP_MSDBSTARTUP','SLEEP_SYSTEMTASK','SLEEP_TASK',
            'SLEEP_TEMPDBSTARTUP','SNI_HTTP_ACCEPT','SOS_WORK_DISPATCHER',
            'SP_SERVER_DIAGNOSTICS_SLEEP','SQLTRACE_BUFFER_FLUSH',
            'SQLTRACE_INCREMENTAL_FLUSH_SLEEP','SQLTRACE_WAIT_ENTRIES','WAIT_FOR_RESULTS',
            'WAITFOR','WAITFOR_TASKSHUTDOWN','WAIT_XTP_RECOVERY','WAIT_XTP_HOST_WAIT',
            'WAIT_XTP_OFFLINE_CKPT_NEW_LOG','WAIT_XTP_CKPT_CLOSE','XE_DISPATCHER_JOIN',
            'XE_DISPATCHER_WAIT','XE_TIMER_EVENT'
        )
        """;

    // Dapper mapira po imenima svojstava; imena polja ValueTuple-a ne postoje u
    // runtime metapodacima, pa se za rezultate koriste eksplicitni tipovi.
    private sealed record CpuRow(long CpuMs, int SchedulerCount);

    private sealed record WaitRow(string WaitType, long WaitTimeMs, long SignalWaitTimeMs, long WaitingTasksCount);

    /// <summary>Uzima snapshot CPU brojača i kumulativnih čekanja.</summary>
    public async Task<ResourceSnapshot> CaptureAsync(CancellationToken ct = default)
    {
        await using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync(ct);

        // total_cpu_usage_ms je kumulativni CPU po scheduleru (SQL Server 2016+).
        // VISIBLE ONLINE isključuje DAC i skrivene schedulere za sistemske zadatke.
        var cpu = await conn.QuerySingleAsync<CpuRow>(
            new CommandDefinition("""
                SELECT
                    CpuMs          = ISNULL(SUM(CONVERT(BIGINT, total_cpu_usage_ms)), 0),
                    SchedulerCount = COUNT(*)
                FROM sys.dm_os_schedulers
                WHERE status = 'VISIBLE ONLINE';
                """, commandTimeout: 30, cancellationToken: ct));

        var waits = await conn.QueryAsync<WaitRow>(
            new CommandDefinition($"""
                SELECT
                    WaitType          = wait_type,
                    WaitTimeMs        = CONVERT(BIGINT, wait_time_ms),
                    SignalWaitTimeMs  = CONVERT(BIGINT, signal_wait_time_ms),
                    WaitingTasksCount = CONVERT(BIGINT, waiting_tasks_count)
                FROM sys.dm_os_wait_stats
                WHERE {BenignWaitFilter};
                """, commandTimeout: 30, cancellationToken: ct));

        return new ResourceSnapshot
        {
            TakenAtUtc     = DateTime.UtcNow,
            SchedulerCpuMs = cpu.CpuMs,
            SchedulerCount = cpu.SchedulerCount,
            Waits = waits.ToDictionary(
                w => w.WaitType,
                w => new WaitCounters(w.WaitTimeMs, w.SignalWaitTimeMs, w.WaitingTasksCount))
        };
    }

    /// <summary>
    /// Računa potrošnju resursa i delte čekanja između dva snapshota.
    /// Negativne delte (koje nastaju ako je netko izvršio DBCC SQLPERF reset
    /// ili je instanca restartovana) tretiraju se kao nula.
    /// </summary>
    public static (ResourceUsage Usage, List<WaitDelta> Waits) Diff(
        ResourceSnapshot before,
        ResourceSnapshot after)
    {
        double windowMs = (after.TakenAtUtc - before.TakenAtUtc).TotalMilliseconds;

        var deltas = new List<WaitDelta>();
        long totalWaitMs = 0;
        long totalSignalMs = 0;

        foreach (var (waitType, afterCounters) in after.Waits)
        {
            before.Waits.TryGetValue(waitType, out var beforeCounters);

            long waitMs   = Math.Max(0, afterCounters.WaitTimeMs       - beforeCounters.WaitTimeMs);
            long signalMs = Math.Max(0, afterCounters.SignalWaitTimeMs - beforeCounters.SignalWaitTimeMs);
            long tasks    = Math.Max(0, afterCounters.WaitingTasksCount - beforeCounters.WaitingTasksCount);

            if (waitMs == 0 && tasks == 0) continue;

            totalWaitMs   += waitMs;
            totalSignalMs += signalMs;

            deltas.Add(new WaitDelta
            {
                WaitType          = waitType,
                WaitTimeMs        = waitMs,
                SignalWaitTimeMs  = signalMs,
                WaitingTasksCount = tasks
            });
        }

        var usage = new ResourceUsage
        {
            WindowMs          = windowMs,
            SchedulerCount    = after.SchedulerCount,
            SqlCpuMs          = Math.Max(0, after.SchedulerCpuMs - before.SchedulerCpuMs),
            TotalWaitMs       = totalWaitMs,
            TotalSignalWaitMs = totalSignalMs
        };

        var topWaits = deltas
            .OrderByDescending(d => d.WaitTimeMs)
            .Take(TopWaitsPerRun)
            .ToList();

        return (usage, topWaits);
    }
}
