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

    /// <param name="procSuffix">
    /// Sufiks imena procedure za kontrolne ruke eksperimenta (npr. "_D2" →
    /// im.usp_OLAP_Q1_MonthlyActivity_D2). Prazno = standardne procedure.
    /// </param>
    public static string GetQuery(string schema, string queryName, string procSuffix = "") =>
        $"EXEC {schema}.usp_OLAP_{queryName}{procSuffix};";

    public static string SelectQueryName(Random rng) =>
        QueryNames[rng.Next(QueryNames.Length)];
}
