-- =============================================================================
-- HTAPBenchmark: 10_MaxDop_Control_Variants.sql
--
-- SVRHA: izolacija confounding varijable stepena paralelizma u usporedbi H3
--        (HTAP naspram IM).
--
-- PROBLEM: u glavnom eksperimentu IM koristi OPTION(MAXDOP 1) zbog CXSYNC_PORT
--          čekanja na Hekaton tablicama, dok HTAP koristi OPTION(MAXDOP 2).
--          Izmjereni jaz u OLTP propusnosti (3,3-6,9x) stoga miješa dva efekta:
--            (a) dual-store arhitekturu (analitika izvan Hekaton sloja), i
--            (b) razliku u stepenu paralelizma analitičkih upita.
--          Bez kontrole, doprinos (b) nije poznat.
--
-- RJEŠENJE: ovaj skript kreira _MD1 i _MD2 varijante svih pet OLAP procedura za
--           obje sheme, čime se omogućava pun 2x2 faktorijalni kontrolni
--           eksperiment:
--
--                        | MAXDOP 1        | MAXDOP 2
--             -----------+-----------------+-----------------
--             IM         | im_MD1          | im_MD2
--             HTAP       | htap_MD1        | htap_MD2
--
--           Ključna usporedba je im_MD1 naspram htap_MD1: pri identičnom stepenu
--           paralelizma svaka preostala razlika pripisiva je isključivo tome gdje
--           se analitika izvršava (Hekaton row-mode naspram columnstore batch-mode),
--           a ne paralelizmu.
--
-- NAPOMENA: procedure su znak-po-znak identične onima iz 09_Fix_OLAP_MaxDop.sql;
--           razlikuju se isključivo po vrijednosti u OPTION(MAXDOP n) i po sufiksu
--           imena. im.* procedure čitaju im.* tablice (Hekaton), htap.* procedure
--           čitaju cs.* tablice (disk + columnstore) — kao u glavnom eksperimentu.
--
-- OČEKIVANJE: im_MD2 može biti sporiji od im_MD1 zbog CXSYNC_PORT čekanja na
--           memorijsko-optimiziranim tablicama. To je legitiman nalaz, a ne greška
--           mjerenja — upravo je taj efekt i bio razlog originalnog izbora MAXDOP 1.
--
-- Pokretanje: nakon 09_Fix_OLAP_MaxDop.sql
-- =============================================================================

USE HTAPBenchmark;
GO

PRINT '--- Kreiranje MAXDOP kontrolnih varijanti (im, htap) ---';
GO

-- =============================================================================
-- im shema, MAXDOP 1  (izvor: im.* memorijsko-optimizirane tablice)
-- =============================================================================
CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity_MD1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors_MD1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution_MD1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer_MD1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity_MD1 AS BEGIN
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

-- =============================================================================
-- im shema, MAXDOP 2  (kontrolni uvjet — očekuje se CXSYNC_PORT čekanje)
-- =============================================================================
CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity_MD2 AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM im.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors_MD2 AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM im.Users u
    INNER JOIN im.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution_MD2 AS BEGIN
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
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer_MD2 AS BEGIN
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
    OPTION (MAXDOP 2);
END;
GO

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity_MD2 AS BEGIN
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
    OPTION (MAXDOP 2);
END;
GO

-- =============================================================================
-- htap shema, MAXDOP 1  (KLJUČNI KONTROLNI UVJET — izvor: cs.* columnstore)
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity_MD1 AS BEGIN
    SET NOCOUNT ON;
    SELECT YEAR(CreationDate) AS Godina, MONTH(CreationDate) AS Mjesec, PostTypeId,
        COUNT(*) AS BrojPostova, AVG(CAST(Score AS FLOAT)) AS ProsjekScore,
        SUM(CAST(ViewCount AS BIGINT)) AS UkupnoPregleda, SUM(AnswerCount) AS UkupnoOdgovora
    FROM cs.Posts
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors_MD1 AS BEGIN
    SET NOCOUNT ON;
    SELECT TOP 50 u.Id, u.DisplayName, u.Reputation,
        COUNT(p.Id) AS BrojOdgovora, AVG(CAST(p.Score AS FLOAT)) AS ProsjekScoreOdgovora,
        SUM(p.FavoriteCount) AS UkupnoFavorita, MAX(p.CreationDate) AS ZadnjiOdgovor
    FROM cs.Users u
    INNER JOIN cs.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution_MD1 AS BEGIN
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
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer_MD1 AS BEGIN
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
    OPTION (MAXDOP 1);
END;
GO

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity_MD1 AS BEGIN
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
    OPTION (MAXDOP 1);
END;
GO

-- =============================================================================
-- htap shema, MAXDOP 2  (odgovara glavnom eksperimentu)
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity_MD2 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors_MD2 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution_MD2 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer_MD2 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity_MD2 AS BEGIN
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

-- =============================================================================
-- Verifikacija: očekuje se 20 procedura (2 sheme x 5 upita x 2 varijante)
-- =============================================================================
SELECT
    Shema    = SCHEMA_NAME(schema_id),
    Varijanta = RIGHT(name, 3),
    Broj     = COUNT(*) OVER (PARTITION BY SCHEMA_NAME(schema_id), RIGHT(name, 3)),
    Naziv    = name
FROM sys.procedures
WHERE name LIKE 'usp[_]OLAP[_]%[_]MD[12]'
ORDER BY Shema, Varijanta, Naziv;
GO

PRINT 'MAXDOP kontrolne varijante kreirane (im/htap x MD1/MD2).';
GO
