-- =============================================================================
-- HTAPBenchmark: 07_StoredProcs_OLAP.sql
-- Analitički upiti (OLAP workload) za sve 4 konfiguracije
--
-- Q1: Aktivnost postova po mjesecu i tipu (trend analiza)
-- Q2: Top 50 korisnika po doprinosu (odgovori + score)
-- Q3: Distribucija glasanja po score bucketu posta
-- Q4: Prosječno vrijeme do prvog odgovora (accept latency)
-- Q5: Korisničke kohort aktivnosti (user engagement)
--
-- Columnstore indeks ubrzava Q1-Q5 kroz batch mode processing.
-- Na BASELINE konfiguraciji isti upiti koriste row mode (sporije za agregacije).
-- =============================================================================

USE HTAPBenchmark;
GO

-- ===========================================================================
-- Q1: Aktivnost postova po mjesecu i tipu
-- Aggregira milijune redova, idealna za columnstore scan
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q1_MonthlyActivity
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(CreationDate)    AS [Godina],
        MONTH(CreationDate)   AS [Mjesec],
        PostTypeId,
        COUNT(*)              AS BrojPostova,
        AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda,
        SUM(AnswerCount)      AS UkupnoOdgovora
    FROM baseline.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q1_MonthlyActivity
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(CreationDate)    AS [Godina],
        MONTH(CreationDate)   AS [Mjesec],
        PostTypeId,
        COUNT(*)              AS BrojPostova,
        AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda,
        SUM(AnswerCount)      AS UkupnoOdgovora
    FROM cs.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId;
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(CreationDate)    AS [Godina],
        MONTH(CreationDate)   AS [Mjesec],
        PostTypeId,
        COUNT(*)              AS BrojPostova,
        AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda,
        SUM(AnswerCount)      AS UkupnoOdgovora
    FROM im.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId;
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(CreationDate)    AS [Godina],
        MONTH(CreationDate)   AS [Mjesec],
        PostTypeId,
        COUNT(*)              AS BrojPostova,
        AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda,
        SUM(AnswerCount)      AS UkupnoOdgovora
    FROM htap.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId;
END;
GO

-- ===========================================================================
-- Q2: Top 50 korisnika po doprinosu odgovora
-- JOIN između Posts i Users, agregacija + sortiranje
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q2_TopContributors
AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50
        u.Id,
        u.DisplayName,
        u.Reputation,
        COUNT(p.Id)                       AS BrojOdgovora,
        AVG(CAST(p.Score AS FLOAT))       AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount)              AS UkupnoFavorita,
        MAX(p.CreationDate)               AS ZadnjiOdgovor
    FROM baseline.Users  u
    INNER JOIN baseline.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q2_TopContributors
AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50
        u.Id,
        u.DisplayName,
        u.Reputation,
        COUNT(p.Id)                       AS BrojOdgovora,
        AVG(CAST(p.Score AS FLOAT))       AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount)              AS UkupnoFavorita,
        MAX(p.CreationDate)               AS ZadnjiOdgovor
    FROM cs.Users  u
    INNER JOIN cs.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC;
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors
AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50
        u.Id,
        u.DisplayName,
        u.Reputation,
        COUNT(p.Id)                       AS BrojOdgovora,
        AVG(CAST(p.Score AS FLOAT))       AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount)              AS UkupnoFavorita,
        MAX(p.CreationDate)               AS ZadnjiOdgovor
    FROM im.Users  u
    INNER JOIN im.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC;
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors
AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50
        u.Id,
        u.DisplayName,
        u.Reputation,
        COUNT(p.Id)                       AS BrojOdgovora,
        AVG(CAST(p.Score AS FLOAT))       AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount)              AS UkupnoFavorita,
        MAX(p.CreationDate)               AS ZadnjiOdgovor
    FROM htap.Users  u
    INNER JOIN htap.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC;
END;
GO

-- ===========================================================================
-- Q3: Distribucija glasanja po score bucketu posta
-- Veliki JOIN (Votes + Posts), grupiranje, histogramska analiza
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q3_VoteDistribution
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END                    AS ScoreBucket,
        v.VoteTypeId,
        COUNT(*)               AS BrojGlasova,
        COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM baseline.Votes v
    INNER JOIN baseline.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END,
        v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q3_VoteDistribution
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END                    AS ScoreBucket,
        v.VoteTypeId,
        COUNT(*)               AS BrojGlasova,
        COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM cs.Votes v
    INNER JOIN cs.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END,
        v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId;
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END                    AS ScoreBucket,
        v.VoteTypeId,
        COUNT(*)               AS BrojGlasova,
        COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM im.Votes v
    INNER JOIN im.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END,
        v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId;
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END                    AS ScoreBucket,
        v.VoteTypeId,
        COUNT(*)               AS BrojGlasova,
        COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM htap.Votes v
    INNER JOIN htap.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE
            WHEN p.Score < 0    THEN 'a_Negativan'
            WHEN p.Score = 0    THEN 'b_Nula'
            WHEN p.Score <= 5   THEN 'c_1-5'
            WHEN p.Score <= 20  THEN 'd_6-20'
            WHEN p.Score <= 100 THEN 'e_21-100'
            ELSE                     'f_100plus'
        END,
        v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId;
END;
GO

-- ===========================================================================
-- Q4: Prosječno vrijeme do prihvaćenog odgovora po mjesecu
-- Self-JOIN na Posts tablici (pitanja + odgovori)
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q4_TimeToAnswer
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(q.CreationDate)    AS Godina,
        MONTH(q.CreationDate)   AS Mjesec,
        COUNT(q.Id)             AS BrojPitanja,
        COUNT(a.Id)             AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END)      AS ProsjecnoSatiDoOdgovora
    FROM baseline.Posts q
    LEFT JOIN baseline.Posts a
        ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q4_TimeToAnswer
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(q.CreationDate)    AS Godina,
        MONTH(q.CreationDate)   AS Mjesec,
        COUNT(q.Id)             AS BrojPitanja,
        COUNT(a.Id)             AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END)      AS ProsjecnoSatiDoOdgovora
    FROM cs.Posts q
    LEFT JOIN cs.Posts a
        ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec;
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(q.CreationDate)    AS Godina,
        MONTH(q.CreationDate)   AS Mjesec,
        COUNT(q.Id)             AS BrojPitanja,
        COUNT(a.Id)             AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END)      AS ProsjecnoSatiDoOdgovora
    FROM im.Posts q
    LEFT JOIN im.Posts a
        ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec;
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer
AS BEGIN
    SET NOCOUNT ON;
    SELECT
        YEAR(q.CreationDate)    AS Godina,
        MONTH(q.CreationDate)   AS Mjesec,
        COUNT(q.Id)             AS BrojPitanja,
        COUNT(a.Id)             AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END)      AS ProsjecnoSatiDoOdgovora
    FROM htap.Posts q
    LEFT JOIN htap.Posts a
        ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec;
END;
GO

-- ===========================================================================
-- Q5: Korisničke kohort aktivnosti (engagement po kvartalu)
-- CTE + agregacija, simulira BI upit na korisničkim podacima
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q5_UserCohortActivity
AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT
            OwnerUserId,
            YEAR(CreationDate)                        AS Godina,
            DATEPART(QUARTER, CreationDate)           AS Kvartal,
            COUNT(*)                                  AS BrojPostova,
            SUM(Score)                                AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM baseline.Posts
        WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT
        Godina,
        Kvartal,
        COUNT(DISTINCT OwnerUserId)         AS AktivniKorisnici,
        SUM(BrojPostova)                    AS UkupnoPostova,
        AVG(CAST(BrojPostova AS FLOAT))     AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore)                    AS UkupniScore,
        SUM(BrojPitanja)                    AS UkupnoPitanja,
        SUM(BrojOdgovora)                   AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q5_UserCohortActivity
AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT
            OwnerUserId,
            YEAR(CreationDate)                        AS Godina,
            DATEPART(QUARTER, CreationDate)           AS Kvartal,
            COUNT(*)                                  AS BrojPostova,
            SUM(Score)                                AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM cs.Posts
        WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT
        Godina, Kvartal,
        COUNT(DISTINCT OwnerUserId)         AS AktivniKorisnici,
        SUM(BrojPostova)                    AS UkupnoPostova,
        AVG(CAST(BrojPostova AS FLOAT))     AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore)                    AS UkupniScore,
        SUM(BrojPitanja)                    AS UkupnoPitanja,
        SUM(BrojOdgovora)                   AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal;
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity
AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT
            OwnerUserId,
            YEAR(CreationDate)                        AS Godina,
            DATEPART(QUARTER, CreationDate)           AS Kvartal,
            COUNT(*)                                  AS BrojPostova,
            SUM(Score)                                AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM im.Posts
        WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT
        Godina, Kvartal,
        COUNT(DISTINCT OwnerUserId)         AS AktivniKorisnici,
        SUM(BrojPostova)                    AS UkupnoPostova,
        AVG(CAST(BrojPostova AS FLOAT))     AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore)                    AS UkupniScore,
        SUM(BrojPitanja)                    AS UkupnoPitanja,
        SUM(BrojOdgovora)                   AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal;
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity
AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT
            OwnerUserId,
            YEAR(CreationDate)                        AS Godina,
            DATEPART(QUARTER, CreationDate)           AS Kvartal,
            COUNT(*)                                  AS BrojPostova,
            SUM(Score)                                AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM htap.Posts
        WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT
        Godina, Kvartal,
        COUNT(DISTINCT OwnerUserId)         AS AktivniKorisnici,
        SUM(BrojPostova)                    AS UkupnoPostova,
        AVG(CAST(BrojPostova AS FLOAT))     AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore)                    AS UkupniScore,
        SUM(BrojPitanja)                    AS UkupnoPitanja,
        SUM(BrojOdgovora)                   AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal;
END;
GO

PRINT 'OLAP stored procedure za sve 4 konfiguracije uspješno kreirane.';
GO
