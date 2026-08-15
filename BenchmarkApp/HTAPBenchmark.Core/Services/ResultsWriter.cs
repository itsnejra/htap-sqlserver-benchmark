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

    // Instrumentacijski izlazi. Odvojene datoteke, a ne dodatne kolone u
    // summary.csv, da postojećih 1.070 mjerenja i analitičke skripte koje ih
    // čitaju ostanu upotrebljivi bez izmjena.
    private readonly StreamWriter? _resourceWriter;
    private readonly StreamWriter? _waitsWriter;
    private readonly StreamWriter? _syncWriter;
    private bool _resourceHeaderWritten;
    private bool _waitsHeaderWritten;
    private bool _syncHeaderWritten;
    private readonly object _resourceLock = new();
    private readonly object _waitsLock = new();
    private readonly object _syncLock = new();

    public ResultsWriter(
        string measurementsCsvPath,
        string summaryCsvPath,
        string? resourceUsageCsvPath = null,
        string? waitStatsCsvPath = null,
        string? syncCyclesCsvPath = null)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(measurementsCsvPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(summaryCsvPath)!);

        // Append mode: preserve existing data so resume logic works correctly.
        // Header is NOT re-written if the file already has content.
        _measurementsWriter        = new StreamWriter(measurementsCsvPath, append: true, Encoding.UTF8);
        _summaryWriter             = new StreamWriter(summaryCsvPath,      append: true, Encoding.UTF8);
        _measurementsHeaderWritten = HasContent(measurementsCsvPath);
        _summaryHeaderWritten      = HasContent(summaryCsvPath);

        (_resourceWriter, _resourceHeaderWritten) = OpenOptional(resourceUsageCsvPath);
        (_waitsWriter,    _waitsHeaderWritten)    = OpenOptional(waitStatsCsvPath);
        (_syncWriter,     _syncHeaderWritten)     = OpenOptional(syncCyclesCsvPath);
    }

    /// <summary>
    /// Ima li datoteka stvarni sadržaj, a ne samo UTF-8 BOM.
    ///
    /// Dužina fajla nije dovoljna provjera: StreamWriter upisuje BOM (3 bajta) i kad
    /// nijedan red nije zapisan — npr. ako run padne pri konektovanju ili se benchmark
    /// prekine odmah po pokretanju. Takav fajl bi po dužini prošao kao "ima sadržaj",
    /// pa bi sljedeće pokretanje preskočilo zaglavlje i proizvelo CSV bez header reda,
    /// koji analitičke skripte ne mogu parsirati.
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
            // Ako datoteku ne možemo pročitati, sigurnije je upisati zaglavlje
            // (suvišan header je uočljiv; nedostajući tiho kvari parsiranje).
            return false;
        }
    }

    private static (StreamWriter?, bool) OpenOptional(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return (null, false);

        var dir = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

        bool hasContent = HasContent(path);
        return (new StreamWriter(path, append: true, Encoding.UTF8), hasContent);
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
                    "OltpSuccessRate,OlapSuccessRate,OltpTotalOps,OlapTotalOps");
                _summaryHeaderWritten = true;
            }

            _summaryWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{summary.Configuration},{summary.OltpOlapRatio},{summary.ConcurrencyLevel},{summary.RunNumber}," +
                $"{summary.OltpThroughput:F4},{summary.OlapThroughput:F4}," +
                $"{summary.OltpLatencyP50:F4},{summary.OltpLatencyP95:F4},{summary.OltpLatencyP99:F4}," +
                $"{summary.OlapLatencyP50:F4},{summary.OlapLatencyP95:F4},{summary.OlapLatencyP99:F4}," +
                $"{summary.OltpSuccessRate:F4},{summary.OlapSuccessRate:F4}," +
                $"{summary.OltpTotalOps},{summary.OlapTotalOps}"));

            _summaryWriter.Flush();
        }
    }

    public void WriteResourceUsage(ResourceUsage usage)
    {
        if (_resourceWriter is null) return;

        lock (_resourceLock)
        {
            if (!_resourceHeaderWritten)
            {
                _resourceWriter.WriteLine(
                    "ExperimentTag,Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "OlapMaxDop,SyncIntervalSeconds,WindowMs,SchedulerCount," +
                    "SqlCpuMs,SqlCpuUtilPct,TotalWaitMs,TotalSignalWaitMs,SignalWaitPct");
                _resourceHeaderWritten = true;
            }

            _resourceWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{usage.ExperimentTag},{usage.Configuration},{usage.OltpOlapRatio}," +
                $"{usage.ConcurrencyLevel},{usage.RunNumber}," +
                $"{usage.OlapMaxDop},{usage.SyncIntervalSeconds}," +
                $"{usage.WindowMs:F1},{usage.SchedulerCount}," +
                $"{usage.SqlCpuMs},{usage.SqlCpuUtilPct:F3}," +
                $"{usage.TotalWaitMs},{usage.TotalSignalWaitMs},{usage.SignalWaitPct:F3}"));

            _resourceWriter.Flush();
        }
    }

    public void WriteWaits(IEnumerable<WaitDelta> waits)
    {
        if (_waitsWriter is null) return;

        lock (_waitsLock)
        {
            if (!_waitsHeaderWritten)
            {
                _waitsWriter.WriteLine(
                    "ExperimentTag,Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "OlapMaxDop,SyncIntervalSeconds,WaitType,WaitTimeMs,SignalWaitTimeMs,WaitingTasksCount");
                _waitsHeaderWritten = true;
            }

            foreach (var w in waits)
            {
                _waitsWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                    $"{w.ExperimentTag},{w.Configuration},{w.OltpOlapRatio}," +
                    $"{w.ConcurrencyLevel},{w.RunNumber}," +
                    $"{w.OlapMaxDop},{w.SyncIntervalSeconds}," +
                    $"{w.WaitType},{w.WaitTimeMs},{w.SignalWaitTimeMs},{w.WaitingTasksCount}"));
            }

            _waitsWriter.Flush();
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
                    "ExperimentTag,Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "SyncIntervalSeconds,CycleNumber,DurationMs," +
                    "VotesPropagated,CommentsPropagated,PostsUpdated," +
                    "AvgFreshnessLagMs,MaxFreshnessLagMs,Success");
                _syncHeaderWritten = true;
            }

            foreach (var c in cycles)
            {
                _syncWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                    $"{c.ExperimentTag},{c.Configuration},{c.OltpOlapRatio}," +
                    $"{c.ConcurrencyLevel},{c.RunNumber}," +
                    $"{c.SyncIntervalSeconds},{c.CycleNumber},{c.DurationMs:F2}," +
                    $"{c.VotesPropagated},{c.CommentsPropagated},{c.PostsUpdated}," +
                    $"{c.AvgFreshnessLagMs:F1},{c.MaxFreshnessLagMs:F1},{(c.Success ? 1 : 0)}"));
            }

            _syncWriter.Flush();
        }
    }

    public void Dispose()
    {
        _measurementsWriter.Dispose();
        _summaryWriter.Dispose();
        _resourceWriter?.Dispose();
        _waitsWriter?.Dispose();
        _syncWriter?.Dispose();
    }
}
