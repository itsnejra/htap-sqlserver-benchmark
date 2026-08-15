using Dapper;
using HTAPBenchmark.Core.Models;
using Microsoft.Data.SqlClient;

namespace HTAPBenchmark.Core.Services;

/// <summary>
/// Provjerava da aktivna shema sadrži očekivani broj redova prije nego mjerenje počne.
///
/// ZAŠTO POSTOJI: im.* i htap.* tablice su DURABILITY = SCHEMA_ONLY, pa gube SVE
/// podatke pri svakom restartu SQL Servera. Ako se 05b_LoadData_CS_HTAP_Only.sql ne
/// pokrene nakon restarta, benchmark radi nad djelimično praznim tablicama i uredno
/// proizvodi brojke — samo neuporedive s ostatkom eksperimenta. OLAP upiti skeniraju
/// manje redova, pa i OLTP i OLAP izgledaju višestruko brži.
///
/// Takav run se ne prepozna po greškama nego tek po tome što su rezultati "predobri",
/// a do tada su potrošeni sati mjerenja. Zato se provjera radi unaprijed i, pri
/// odstupanju, prekida pokretanje umjesto da ga pusti.
///
/// LoadWorkloadContextAsync ovo ne hvata: on traži TOP 20000 postova, što uspijeva
/// i kad tablica ima 20.000 umjesto 3,7 miliona redova.
/// </summary>
public static class DatasetIntegrityCheck
{
    /// <summary>
    /// Očekivani broj redova po tablici u StackOverflow2010 skupu. Iste vrijednosti
    /// su navedene u radu (Tabela "Veličine tabela u skupu podataka StackOverflow2010").
    /// </summary>
    public static readonly IReadOnlyDictionary<string, int> ExpectedRows = new Dictionary<string, int>
    {
        ["Posts"]    = 3_729_195,
        ["Users"]    =   299_398,
        ["Votes"]    = 10_143_364,
        ["Comments"] =  3_875_183,
        ["Badges"]   =  1_102_019,
    };

    /// <summary>
    /// Dopušteno odstupanje. Benchmark tokom rada dodaje glasove i komentare, a
    /// cleanup ih briše po vodenom žigu, pa se stvarni broj redova može razlikovati
    /// za nekoliko postotaka bez ikakvog problema. Prag hvata razliku reda veličine
    /// (prazna ili djelimično učitana tablica), ne šum.
    /// </summary>
    public const double ToleranceFraction = 0.05;

    public sealed record TableCount(string Table, long Actual, long Expected)
    {
        public double Ratio => Expected > 0 ? (double)Actual / Expected : 0;
        public bool IsOk => Math.Abs(Ratio - 1.0) <= ToleranceFraction;
    }

    public sealed record Report(string Schema, IReadOnlyList<TableCount> Tables)
    {
        public bool IsOk => Tables.All(t => t.IsOk);
        public IEnumerable<TableCount> Problems => Tables.Where(t => !t.IsOk);
    }

    public static async Task<Report> VerifyAsync(
        string connectionString, string schema, CancellationToken ct = default)
    {
        await using var conn = new SqlConnection(connectionString);
        await conn.OpenAsync(ct);

        var rows = new List<TableCount>();

        foreach (var (table, expected) in ExpectedRows)
        {
            // MAXDOP 1: paralelni planovi nad memorijsko-optimiziranim tablicama
            // izazivaju CXSYNC_PORT čekanje (isti razlog kao u LoadWorkloadContextAsync).
            long actual = await conn.ExecuteScalarAsync<long>(
                new CommandDefinition(
                    $"SELECT COUNT_BIG(*) FROM {schema}.{table} OPTION (MAXDOP 1);",
                    commandTimeout: 300, cancellationToken: ct));

            rows.Add(new TableCount(table, actual, expected));
        }

        return new Report(schema, rows);
    }

    /// <summary>Poruka za log; nabraja samo tablice koje odstupaju.</summary>
    public static string DescribeProblems(Report report)
    {
        var lines = report.Problems.Select(p =>
            $"    {report.Schema}.{p.Table,-9} {p.Actual,12:N0} redova, očekivano {p.Expected,12:N0} " +
            $"({p.Ratio * 100:F1} % očekivanog)");

        return string.Join(Environment.NewLine, lines);
    }
}
