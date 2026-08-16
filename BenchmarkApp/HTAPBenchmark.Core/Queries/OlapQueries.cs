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

    /// <summary>
    /// Gradi EXEC poziv za zadanu shemu i upit.
    /// </summary>
    /// <param name="suffix">
    /// Opcionalni sufiks imena procedure (npr. "_Dop1"). Koristi se u kontrolnom
    /// eksperimentu za H3, gdje HTAP izvodi analitiku pri istom stepenu paralelizma
    /// kao IM (MAXDOP 1), da bi se razlika u propusnosti pripisala arhitekturi
    /// pohrane, a ne razlici u paralelizmu. Prazan sufiks daje originalne procedure.
    /// </param>
    public static string GetQuery(string schema, string queryName, string suffix = "")
    {
        string procedure = queryName switch
        {
            "Q1_MonthlyActivity"    => "usp_OLAP_Q1_MonthlyActivity",
            "Q2_TopContributors"    => "usp_OLAP_Q2_TopContributors",
            "Q3_VoteDistribution"   => "usp_OLAP_Q3_VoteDistribution",
            "Q4_TimeToAnswer"       => "usp_OLAP_Q4_TimeToAnswer",
            "Q5_UserCohortActivity" => "usp_OLAP_Q5_UserCohortActivity",
            _ => throw new ArgumentOutOfRangeException(nameof(queryName))
        };

        return $"EXEC {schema}.{procedure}{suffix};";
    }

    public static string SelectQueryName(Random rng) =>
        QueryNames[rng.Next(QueryNames.Length)];
}
