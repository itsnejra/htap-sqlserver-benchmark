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

    public ResultsWriter(string measurementsCsvPath, string summaryCsvPath)
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

    public void Dispose()
    {
        _measurementsWriter.Dispose();
        _summaryWriter.Dispose();
    }
}
