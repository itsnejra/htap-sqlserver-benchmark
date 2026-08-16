using System.Globalization;
using System.Text;
using HTAPBenchmark.Core.Models;

namespace HTAPBenchmark.Core.Services;

public sealed class ResultsWriter : IDisposable
{
    private readonly StreamWriter _measurementsWriter;
    private readonly StreamWriter _summaryWriter;
    private readonly StreamWriter? _resourcesWriter;
    private bool _measurementsHeaderWritten;
    private bool _summaryHeaderWritten;
    private bool _resourcesHeaderWritten;
    private readonly object _measurementsLock = new();
    private readonly object _summaryLock = new();
    private readonly object _resourcesLock = new();

    public ResultsWriter(string measurementsCsvPath, string summaryCsvPath, string? resourcesCsvPath = null)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(measurementsCsvPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(summaryCsvPath)!);

        // Append mode: preserve existing data so resume logic works correctly.
        // Header is NOT re-written if the file already has content.
        bool measurementsHasContent = File.Exists(measurementsCsvPath) && new FileInfo(measurementsCsvPath).Length > 0;
        bool summaryHasContent      = File.Exists(summaryCsvPath)      && new FileInfo(summaryCsvPath).Length > 0;

        _measurementsWriter        = new StreamWriter(measurementsCsvPath, append: true, Encoding.UTF8);
        _summaryWriter             = new StreamWriter(summaryCsvPath,      append: true, Encoding.UTF8);
        _measurementsHeaderWritten = measurementsHasContent;
        _summaryHeaderWritten      = summaryHasContent;

        if (!string.IsNullOrWhiteSpace(resourcesCsvPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(resourcesCsvPath)!);
            _resourcesHeaderWritten = File.Exists(resourcesCsvPath) && new FileInfo(resourcesCsvPath).Length > 0;
            _resourcesWriter        = new StreamWriter(resourcesCsvPath, append: true, Encoding.UTF8);
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

    /// <summary>
    /// Zapisuje profil resursa jednog runa: jedan red po (run, wait_type), plus red
    /// TOTAL s agregatnim pokazateljima CPU pritiska. Format je "long" da bi se u
    /// analizi lako filtriralo po tipu čekanja bez fiksne liste kolona.
    /// </summary>
    public void WriteResourceProfile(ResourceProfile profile)
    {
        if (_resourcesWriter is null) return;

        lock (_resourcesLock)
        {
            if (!_resourcesHeaderWritten)
            {
                _resourcesWriter.WriteLine(
                    "Configuration,OltpOlapRatio,ConcurrencyLevel,RunNumber," +
                    "WaitType,WaitingTasksCount,WaitTimeMs,SignalWaitTimeMs," +
                    "AvgRunnableTasksPerScheduler,MaxRunnableTasksPerScheduler," +
                    "AvgActiveWorkersPerScheduler,AvgSqlCpuPercent,MaxSqlCpuPercent," +
                    "AvgTotalCpuPercent,SignalWaitPercent,SampleCount");
                _resourcesHeaderWritten = true;
            }

            string key = string.Create(CultureInfo.InvariantCulture,
                $"{profile.Configuration},{profile.OltpOlapRatio},{profile.ConcurrencyLevel},{profile.RunNumber}");

            string aggregates = string.Create(CultureInfo.InvariantCulture,
                $"{profile.AvgRunnableTasksPerScheduler:F4},{profile.MaxRunnableTasksPerScheduler:F4}," +
                $"{profile.AvgActiveWorkersPerScheduler:F4},{profile.AvgSqlCpuPercent:F4},{profile.MaxSqlCpuPercent:F4}," +
                $"{profile.AvgTotalCpuPercent:F4},{profile.SignalWaitPercent:F4},{profile.SampleCount}");

            _resourcesWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{key},TOTAL,0,{profile.TotalWaitTimeMs:F2},{profile.TotalSignalWaitTimeMs:F2},{aggregates}"));

            foreach (var w in profile.Waits)
            {
                _resourcesWriter.WriteLine(string.Create(CultureInfo.InvariantCulture,
                    $"{key},{w.WaitType},{w.WaitingTasksCount},{w.WaitTimeMs:F2},{w.SignalWaitTimeMs:F2},{aggregates}"));
            }

            _resourcesWriter.Flush();
        }
    }

    public void Dispose()
    {
        _measurementsWriter.Dispose();
        _summaryWriter.Dispose();
        _resourcesWriter?.Dispose();
    }
}
