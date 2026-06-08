namespace HTAPBenchmark.Core.Queries;

public static class OltpQueries
{
    public static string GetPostById(string schema) =>
        $"EXEC {schema}.usp_GetPostById @PostId;";

    public static string GetUserById(string schema) =>
        $"EXEC {schema}.usp_GetUserById @UserId;";

    public static string InsertVote(string schema) =>
        $"EXEC {schema}.usp_InsertVote @Id, @PostId, @VoteTypeId, @CreationDate, @UserId;";

    public static string UpdatePostScore(string schema) =>
        $"EXEC {schema}.usp_UpdatePostScore @PostId, @Delta;";

    public static string InsertComment(string schema) =>
        $"EXEC {schema}.usp_InsertComment @Id, @PostId, @Score, @Text, @CreationDate, @UserId;";

    public static string GetRecentUserPosts(string schema) =>
        $"EXEC {schema}.usp_GetRecentUserPosts @UserId;";

    /// <summary>
    /// Simple DELETE — briše jedan glas po primarnom ključu.
    /// ID mora biti iz skupa glasanja koje je benchmark insertovao (Id > OriginalMaxVoteId).
    /// </summary>
    public static string DeleteVote(string schema) =>
        $"EXEC {schema}.usp_DeleteVote @Id;";

    /// <summary>
    /// Complex DELETE — briše sve glasove datog tipa za određeni post.
    /// Simulira povlačenje moderatorskih oznaka s posta (višestruko brisanje).
    /// </summary>
    public static string DeletePostVotes(string schema) =>
        $"EXEC {schema}.usp_DeletePostVotes @PostId, @VoteTypeId;";

    /// <summary>
    /// Complex UPDATE — čita COUNT odgovora korisnika iz Posts, ažurira Users.Reputation.
    /// Pristupa dvjema tablicama; nativno kompajlirano za im/htap.
    /// </summary>
    public static string UpdateUserReputation(string schema) =>
        $"EXEC {schema}.usp_UpdateUserReputation @UserId;";

    // Operacije i njihove relativne težine (ukupno 100)
    // Uključuje puni CRUD pokrivač: SELECT / INSERT / UPDATE / DELETE (Simple + Complex)
    public static readonly (string Name, int Weight)[] Operations =
    [
        ("usp_InsertVote",              30),
        ("usp_UpdatePostScore",         22),
        ("usp_InsertComment",           13),
        ("usp_GetRecentUserPosts",       9),
        ("usp_GetPostById",              9),
        ("usp_GetUserById",              4),
        ("usp_DeleteVote",               7),
        ("usp_DeletePostVotes",          4),
        ("usp_UpdateUserReputation",     2),
    ];

    // Kumulativne težine za weighted random selection
    private static readonly int[] CumulativeWeights;
    static OltpQueries()
    {
        CumulativeWeights = new int[Operations.Length];
        int cumulative = 0;
        for (int i = 0; i < Operations.Length; i++)
        {
            cumulative += Operations[i].Weight;
            CumulativeWeights[i] = cumulative;
        }
    }

    public static string SelectOperationName(Random rng)
    {
        int roll = rng.Next(1, 101);
        for (int i = 0; i < CumulativeWeights.Length; i++)
        {
            if (roll <= CumulativeWeights[i])
                return Operations[i].Name;
        }
        return Operations[^1].Name;
    }
}
