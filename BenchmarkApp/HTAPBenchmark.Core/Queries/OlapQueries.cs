namespace HTAPBenchmark.Core.Queries;

public static class OlapQueries
{
    public static string Q1_MonthlyActivity(string schema) =>
        $"EXEC {schema}.usp_OLAP_Q1_MonthlyActivity;";

    public static string Q2_TopContributors(string schema) =>
        $"EXEC {schema}.usp_OLAP_Q2_TopContributors;";

    public static string Q3_VoteDistribution(string schema) =>
        $"EXEC {schema}.usp_OLAP_Q3_VoteDistribution;";

    public static string Q4_TimeToAnswer(string schema) =>
        $"EXEC {schema}.usp_OLAP_Q4_TimeToAnswer;";

    public static string Q5_UserCohortActivity(string schema) =>
        $"EXEC {schema}.usp_OLAP_Q5_UserCohortActivity;";

    public static readonly string[] QueryNames =
    [
        "Q1_MonthlyActivity",
        "Q2_TopContributors",
        "Q3_VoteDistribution",
        "Q4_TimeToAnswer",
        "Q5_UserCohortActivity"
    ];

    public static string GetQuery(string schema, string queryName) =>
        queryName switch
        {
            "Q1_MonthlyActivity"    => Q1_MonthlyActivity(schema),
            "Q2_TopContributors"    => Q2_TopContributors(schema),
            "Q3_VoteDistribution"   => Q3_VoteDistribution(schema),
            "Q4_TimeToAnswer"       => Q4_TimeToAnswer(schema),
            "Q5_UserCohortActivity" => Q5_UserCohortActivity(schema),
            _ => throw new ArgumentOutOfRangeException(nameof(queryName))
        };

    /// <summary>
    /// Varijanta upita s eksplicitno kontroliranim stepenom paralelizma.
    ///
    /// maxDopVariant = 0 → originalna procedura (MAXDOP kakav je zatečen u shemi:
    ///                     MAXDOP 1 za im, MAXDOP 2 za cs/htap/baseline).
    /// maxDopVariant = 1 ili 2 → _MD1 / _MD2 procedura iz
    ///                     10_MaxDop_Control_Variants.sql.
    ///
    /// Postoji da bi se u usporedbi IM naspram HTAP stepen paralelizma mogao
    /// izjednačiti; bez toga izmjereni jaz miješa efekt dual-store arhitekture s
    /// efektom paralelizma analitičkih upita.
    /// </summary>
    public static string GetQuery(string schema, string queryName, int maxDopVariant)
    {
        if (maxDopVariant == 0)
            return GetQuery(schema, queryName);

        if (maxDopVariant is not (1 or 2))
            throw new ArgumentOutOfRangeException(nameof(maxDopVariant),
                maxDopVariant, "Podržane su samo varijante 0 (originalna), 1 i 2.");

        if (!QueryNames.Contains(queryName))
            throw new ArgumentOutOfRangeException(nameof(queryName));

        return $"EXEC {schema}.usp_OLAP_{queryName}_MD{maxDopVariant};";
    }

    public static string SelectQueryName(Random rng) =>
        QueryNames[rng.Next(QueryNames.Length)];
}
