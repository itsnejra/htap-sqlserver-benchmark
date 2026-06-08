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

    // Operacije i njihove relativne težine (ukupno 100)
    public static readonly (string Name, int Weight)[] Operations =
    [
        ("usp_InsertVote",         35),
        ("usp_UpdatePostScore",    25),
        ("usp_InsertComment",      15),
        ("usp_GetRecentUserPosts", 10),
        ("usp_GetPostById",        10),
        ("usp_GetUserById",         5),
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
