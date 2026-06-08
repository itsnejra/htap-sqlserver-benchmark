using HTAPBenchmark.Core.Models;

namespace HTAPBenchmark.Core.Services;

public static class MetricsCalculator
{
    public static RunSummary Calculate(
        int runId,
        List<MeasurementResult> measurements,
        int measurementSeconds)
    {
        var oltpMeasurements = measurements.Where(m => m.OperationType == "OLTP").ToList();
        var olapMeasurements = measurements.Where(m => m.OperationType == "OLAP").ToList();

        var oltpLatencies = oltpMeasurements.Where(m => m.Success).Select(m => m.LatencyMs).OrderBy(x => x).ToArray();
        var olapLatencies = olapMeasurements.Where(m => m.Success).Select(m => m.LatencyMs).OrderBy(x => x).ToArray();

        var first = measurements.First();

        return new RunSummary
        {
            RunId            = runId,
            Configuration    = first.Configuration,
            OltpOlapRatio    = first.OltpOlapRatio,
            ConcurrencyLevel = first.ConcurrencyLevel,
            RunNumber        = first.RunNumber,

            OltpThroughput   = oltpLatencies.Length / (double)measurementSeconds,
            OlapThroughput   = olapLatencies.Length / (double)measurementSeconds,

            OltpLatencyP50   = Percentile(oltpLatencies, 0.50),
            OltpLatencyP95   = Percentile(oltpLatencies, 0.95),
            OltpLatencyP99   = Percentile(oltpLatencies, 0.99),

            OlapLatencyP50   = Percentile(olapLatencies, 0.50),
            OlapLatencyP95   = Percentile(olapLatencies, 0.95),
            OlapLatencyP99   = Percentile(olapLatencies, 0.99),

            // Min/Avg/Max/Total latencija (zahtjev predmeta: averageExecutionTime,
            // minimumExecutionTime, maximumExecutionTime, totalExecutionTime)
            OltpLatencyMin   = oltpLatencies.Length > 0 ? oltpLatencies[0]    : 0d,
            OltpLatencyAvg   = oltpLatencies.Length > 0 ? oltpLatencies.Average() : 0d,
            OltpLatencyMax   = oltpLatencies.Length > 0 ? oltpLatencies[^1]   : 0d,
            OltpLatencyTotal = oltpLatencies.Sum(),

            OlapLatencyMin   = olapLatencies.Length > 0 ? olapLatencies[0]    : 0d,
            OlapLatencyAvg   = olapLatencies.Length > 0 ? olapLatencies.Average() : 0d,
            OlapLatencyMax   = olapLatencies.Length > 0 ? olapLatencies[^1]   : 0d,
            OlapLatencyTotal = olapLatencies.Sum(),

            // SQL Server CPU i RAM — popunjava BenchmarkOrchestrator pozivom MeasureServerResourcesAsync
            SqlCpuPercent    = 0d,
            SqlMemoryUsedMB  = 0d,

            OltpSuccessRate  = oltpMeasurements.Count == 0 ? 0d :
                               oltpLatencies.Length / (double)oltpMeasurements.Count,
            OlapSuccessRate  = olapMeasurements.Count == 0 ? 0d :
                               olapLatencies.Length / (double)olapMeasurements.Count,

            OltpTotalOps     = oltpMeasurements.Count,
            OlapTotalOps     = olapMeasurements.Count
        };
    }

    private static double Percentile(double[] sortedData, double fraction)
    {
        if (sortedData.Length == 0) return 0d;
        if (sortedData.Length == 1) return sortedData[0];

        double index = fraction * (sortedData.Length - 1);
        int lower = (int)Math.Floor(index);
        int upper = Math.Min(lower + 1, sortedData.Length - 1);
        double weight = index - lower;
        return sortedData[lower] * (1 - weight) + sortedData[upper] * weight;
    }
}
