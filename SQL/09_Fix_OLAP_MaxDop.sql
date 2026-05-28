-- =============================================================================
-- HTAPBenchmark: 09_Fix_OLAP_MaxDop.sql
-- Dodaje OPTION(MAXDOP 2) svim OLAP procedurama da spriječi CPU zagušenje
-- pri visokoj konkurentnosti (C=32 → 6 paralelnih OLAP sesija).
--
-- Bez MAXDOP: svaki upit koristi 6-8 CPU niti (batch mode), 6 sesija = 48 niti
-- Sa MAXDOP 2: svaki upit koristi 2 niti, 6 sesija = 12 niti → bez zagušenja
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================================
-- baseline schema (disk, row mode) - Q1
-- ============================================================================
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q1_MonthlyActivity AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM baseline.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 2);
END;
GO

-- baseline Q2
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q2_TopContributors AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM baseline.Users u
    INNER JOIN baseline.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 2);
END;
GO

-- baseline Q3
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q3_VoteDistribution AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END AS ScoreBucket,
        v.VoteTypeId, COUNT(*) AS BrojGlasova, COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM baseline.Votes v
    INNER JOIN baseline.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END, v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId
    OPTION (MAXDOP 2);
END;
GO

-- baseline Q4
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q4_TimeToAnswer AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(q.CreationDate) AS Godina, MONTH(q.CreationDate) AS Mjesec,
        COUNT(q.Id) AS BrojPitanja, COUNT(a.Id) AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END) AS ProsjecnoSatiDoOdgovora
    FROM baseline.Posts q
    LEFT JOIN baseline.Posts a ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec
    OPTION (MAXDOP 2);
END;
GO

-- baseline Q5
CREATE OR ALTER PROCEDURE baseline.usp_OLAP_Q5_UserCohortActivity AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT OwnerUserId, YEAR(CreationDate) AS Godina,
            DATEPART(QUARTER, CreationDate) AS Kvartal, COUNT(*) AS BrojPostova,
            SUM(Score) AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM baseline.Posts WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT Godina, Kvartal, COUNT(DISTINCT OwnerUserId) AS AktivniKorisnici,
        SUM(BrojPostova) AS UkupnoPostova, AVG(CAST(BrojPostova AS FLOAT)) AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore) AS UkupniScore, SUM(BrojPitanja) AS UkupnoPitanja, SUM(BrojOdgovora) AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal
    OPTION (MAXDOP 2);
END;
GO

-- ============================================================================
-- cs schema (disk + columnstore, batch mode) - Q1-Q5
-- ============================================================================
CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q1_MonthlyActivity AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM cs.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q2_TopContributors AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM cs.Users u
    INNER JOIN cs.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q3_VoteDistribution AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END AS ScoreBucket,
        v.VoteTypeId, COUNT(*) AS BrojGlasova, COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM cs.Votes v
    INNER JOIN cs.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END, v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q4_TimeToAnswer AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(q.CreationDate) AS Godina, MONTH(q.CreationDate) AS Mjesec,
        COUNT(q.Id) AS BrojPitanja, COUNT(a.Id) AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END) AS ProsjecnoSatiDoOdgovora
    FROM cs.Posts q
    LEFT JOIN cs.Posts a ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_OLAP_Q5_UserCohortActivity AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT OwnerUserId, YEAR(CreationDate) AS Godina,
            DATEPART(QUARTER, CreationDate) AS Kvartal, COUNT(*) AS BrojPostova,
            SUM(Score) AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM cs.Posts WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT Godina, Kvartal, COUNT(DISTINCT OwnerUserId) AS AktivniKorisnici,
        SUM(BrojPostova) AS UkupnoPostova, AVG(CAST(BrojPostova AS FLOAT)) AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore) AS UkupniScore, SUM(BrojPitanja) AS UkupnoPitanja, SUM(BrojOdgovora) AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal
    OPTION (MAXDOP 2);
END;
GO

-- ============================================================================
-- im schema (memory-optimized, single-threaded anyway) - Q1-Q5
-- ============================================================================
CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM im.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM im.Users u
    INNER JOIN im.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END AS ScoreBucket,
        v.VoteTypeId, COUNT(*) AS BrojGlasova, COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM im.Votes v
    INNER JOIN im.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END, v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(q.CreationDate) AS Godina, MONTH(q.CreationDate) AS Mjesec,
        COUNT(q.Id) AS BrojPitanja, COUNT(a.Id) AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END) AS ProsjecnoSatiDoOdgovora
    FROM im.Posts q
    LEFT JOIN im.Posts a ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT OwnerUserId, YEAR(CreationDate) AS Godina,
            DATEPART(QUARTER, CreationDate) AS Kvartal, COUNT(*) AS BrojPostova,
            SUM(Score) AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM im.Posts WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT Godina, Kvartal, COUNT(DISTINCT OwnerUserId) AS AktivniKorisnici,
        SUM(BrojPostova) AS UkupnoPostova, AVG(CAST(BrojPostova AS FLOAT)) AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore) AS UkupniScore, SUM(BrojPitanja) AS UkupnoPitanja, SUM(BrojOdgovora) AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal
    OPTION (MAXDOP 1);
END;
GO

-- ============================================================================
-- htap schema - OLAP reads cs.* tables (disk+columnstore) → MAXDOP 2
-- ============================================================================
CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM cs.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM cs.Users u
    INNER JOIN cs.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution AS BEGIN
    SET NOCOUNT ON;
    SELECT
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END AS ScoreBucket,
        v.VoteTypeId, COUNT(*) AS BrojGlasova, COUNT(DISTINCT v.PostId) AS BrojPostova
    FROM cs.Votes v
    INNER JOIN cs.Posts p ON v.PostId = p.Id
    GROUP BY
        CASE WHEN p.Score < 0 THEN 'a_Negativan' WHEN p.Score = 0 THEN 'b_Nula'
             WHEN p.Score <= 5 THEN 'c_1-5' WHEN p.Score <= 20 THEN 'd_6-20'
             WHEN p.Score <= 100 THEN 'e_21-100' ELSE 'f_100plus' END, v.VoteTypeId
    ORDER BY ScoreBucket, v.VoteTypeId
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(q.CreationDate) AS Godina, MONTH(q.CreationDate) AS Mjesec,
        COUNT(q.Id) AS BrojPitanja, COUNT(a.Id) AS PitanjaSaOdgovorom,
        CAST(COUNT(a.Id) AS FLOAT) / COUNT(q.Id) AS StopaOdgovaranja,
        AVG(CASE WHEN a.Id IS NOT NULL
            THEN CAST(DATEDIFF(MINUTE, q.CreationDate, a.CreationDate) AS FLOAT) / 60.0
            ELSE NULL END) AS ProsjecnoSatiDoOdgovora
    FROM cs.Posts q
    LEFT JOIN cs.Posts a ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity AS BEGIN
    SET NOCOUNT ON;
    WITH MonthlyUserActivity AS (
        SELECT OwnerUserId, YEAR(CreationDate) AS Godina,
            DATEPART(QUARTER, CreationDate) AS Kvartal, COUNT(*) AS BrojPostova,
            SUM(Score) AS UkupniScore,
            SUM(CASE WHEN PostTypeId = 1 THEN 1 ELSE 0 END) AS BrojPitanja,
            SUM(CASE WHEN PostTypeId = 2 THEN 1 ELSE 0 END) AS BrojOdgovora
        FROM cs.Posts WHERE OwnerUserId IS NOT NULL
        GROUP BY OwnerUserId, YEAR(CreationDate), DATEPART(QUARTER, CreationDate)
    )
    SELECT Godina, Kvartal, COUNT(DISTINCT OwnerUserId) AS AktivniKorisnici,
        SUM(BrojPostova) AS UkupnoPostova, AVG(CAST(BrojPostova AS FLOAT)) AS ProsjecnoPostovaPoKorisniku,
        SUM(UkupniScore) AS UkupniScore, SUM(BrojPitanja) AS UkupnoPitanja, SUM(BrojOdgovora) AS UkupnoOdgovora
    FROM MonthlyUserActivity
    GROUP BY Godina, Kvartal
    ORDER BY Godina, Kvartal
    OPTION (MAXDOP 2);
END;
GO

PRINT 'OLAP stored procedures updated with OPTION(MAXDOP 2/1).';
GO
