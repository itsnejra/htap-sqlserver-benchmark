using System.Globalization;
using System.Text;
using HTAPBenchmark.Core.Models;

namespace HTAPBenchmark.Core.Services;

public sealed class ResultsWriter : IDisposable
{
    private readonly StreamWriter _measurementsWriter;
    private readonly StreamWriter _summaryWriter;
    private bool _measurementsHeaderWritten;
    private bool _summaryHeaderWritten;
    private readonly object _measurementsLock = new();
    private readonly object _summaryLock = new();

    // Ciklusi sinhronizacije idu u zasebnu datoteku: jedan run ima N ciklusa, pa se
    // ne uklapaju u summary koji ima jedan red po runu.
    private readonly StreamWriter? _syncWriter;
    private bool _syncHeaderWritten;
    private readonly object _syncLock = new();

    public ResultsWriter(string measurementsCsvPath, string summaryCsvPath, string? syncCyclesCsvPath = null)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(measurementsCsvPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(summaryCsvPath)!);

        // Append mode: preserve existing data so resume logic works correctly.
        // Header is NOT re-written if the file already has content.
        _measurementsWriter        = new StreamWriter(measurementsCsvPath, append: true, Encoding.UTF8);
        _summaryWriter             = new StreamWriter(summaryCsvPath,      append: true, Encoding.UTF8);
        _measurementsHeaderWritten = HasContent(measurementsCsvPath);
        _summaryHeaderWritten      = HasContent(summaryCsvPath);

        if (!string.IsNullOrWhiteSpace(syncCyclesCsvPath))
        {
            var dir = Path.GetDirectoryName(syncCyclesCsvPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            _syncHeaderWritten = HasContent(syncCyclesCsvPath);
            _syncWriter        = new StreamWriter(syncCyclesCsvPath, append: true, Encoding.UTF8);
        }
    }

    /// <summary>
    /// Ima li datoteka stvarni sadržaj, a ne samo UTF-8 BOM.
    ///
    /// Dužina fajla nije dovoljna provjera: StreamWriter upisuje BOM (3 bajta) i kad
    /// nijedan red nije zapisan — npr. kad run padne pri konektovanju ili se benchmark
    /// prekine odmah po pokretanju, što se dešava i pri običnom --dry-run bez baze.
    /// Takav fajl bi po dužini prošao kao "ima sadržaj", pa bi sljedeće pokretanje
    /// preskočilo zaglavlje i proizvelo CSV čiji je prvi red podatak. Analitičke
    /// skripte ga tada čitaju kao zaglavlje.
    /// </summary>
    private static bool HasContent(string path)
    {
        if (!File.Exists(path)) return false;

        try
        {
            using var reader = new StreamReader(path, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            return !string.IsNullOrWhiteSpace(reader.ReadLine());
        }
        catch
        {
            // Suvišan header je uočljiv u podacima; nedostajući tiho kvari parsiranje.
            return false;
        }
    }

    public void WriteSyncCycles(IEnumerable<SyncCycleResult> cycles)
    {
        if (_syncWriter is null) return;

        lock (_syncLock)
        {
            if (!_syncHeaderWritten)
            {
                _syncWriter.WriteLine(
                    "Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "SyncIntervalSeconds,CycleNumber,DurationMs," +
                    "VotesPropagated,CommentsPropagated,PostsUpdated," +
                    "AvgFreshnessLagMs,MaxFreshnessLagMs,Success");
                _syncHeaderWritten = true;
            }

            foreach (var c in cycles)
            {
                _syncWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                    $"{c.Configuration},{c.OltpOlapRatio},{c.ConcurrencyLevel},{c.RunNumber}," +
                    $"{c.SyncIntervalSeconds},{c.CycleNumber},{c.DurationMs:F2}," +
                    $"{c.VotesPropagated},{c.CommentsPropagated},{c.PostsUpdated}," +
                    $"{c.AvgFreshnessLagMs:F1},{c.MaxFreshnessLagMs:F1},{(c.Success ? 1 : 0)}"));
            }

            _syncWriter.Flush();
        }
    }

    public void WriteMeasurements(IEnumerable<MeasurementResult> results)
    {
        lock (_measurementsLock)
        {
            if (!_measurementsHeaderWritten)
            {
                _measurementsWriter.WriteLine(
                    "Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "OperationType,OperationName,LatencyMs,Success");
                _measurementsHeaderWritten = true;
            }

            foreach (var r in results)
            {
                _measurementsWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                    $"{r.Configuration},{r.OltpOlapRatio},{r.ConcurrencyLevel},{r.RunNumber}," +
                    $"{r.OperationType},{r.OperationName},{r.LatencyMs:F4},{(r.Success ? 1 : 0)}"));
            }

            _measurementsWriter.Flush();
        }
    }

    public void WriteSummary(RunSummary summary)
    {
        lock (_summaryLock)
        {
            if (!_summaryHeaderWritten)
            {
                _summaryWriter.WriteLine(
                    "Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "OltpThroughput,OlapThroughput," +
                    "OltpLatencyP50,OltpLatencyP95,OltpLatencyP99," +
                    "OlapLatencyP50,OlapLatencyP95,OlapLatencyP99," +
                    "OltpSuccessRate,OlapSuccessRate,OltpTotalOps,OlapTotalOps," +
                    "OltpCpuMs,OlapCpuMs,CpuUtilizationPct,OlapCpuShare," +
                    "SchedulerYieldMs,ParallelismWaitMs,CxSyncPortMs," +
                    "ResourceSemaphoreMs,PageIoLatchMs,WriteLogMs");
                _summaryHeaderWritten = true;
            }

            var sm = summary.ServerMetrics;

            _summaryWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{summary.Configuration},{summary.OltpOlapRatio},{summary.ConcurrencyLevel},{summary.RunNumber}," +
                $"{summary.OltpThroughput:F4},{summary.OlapThroughput:F4}," +
                $"{summary.OltpLatencyP50:F4},{summary.OltpLatencyP95:F4},{summary.OltpLatencyP99:F4}," +
                $"{summary.OlapLatencyP50:F4},{summary.OlapLatencyP95:F4},{summary.OlapLatencyP99:F4}," +
                $"{summary.OltpSuccessRate:F4},{summary.OlapSuccessRate:F4}," +
                $"{summary.OltpTotalOps},{summary.OlapTotalOps}," +
                $"{(sm?.OltpCpuMs ?? 0):F1},{(sm?.OlapCpuMs ?? 0):F1}," +
                $"{(sm?.CpuUtilizationPct ?? 0):F3},{(sm?.OlapCpuShare ?? 0):F4}," +
                $"{(sm?.SchedulerYieldMs ?? 0):F1},{(sm?.ParallelismWaitMs ?? 0):F1},{(sm?.CxSyncPortMs ?? 0):F1}," +
                $"{(sm?.ResourceSemaphoreMs ?? 0):F1},{(sm?.PageIoLatchMs ?? 0):F1},{(sm?.WriteLogMs ?? 0):F1}"));

            _summaryWriter.Flush();
        }
    }

    public void Dispose()
    {
        _measurementsWriter.Dispose();
        _summaryWriter.Dispose();
        _syncWriter?.Dispose();
    }
}
