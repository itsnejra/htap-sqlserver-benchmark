-- =============================================================================
-- HTAPBenchmark: 10_MaxDopControl.sql
--
-- SVRHA: eliminacija MAXDOP confounding varijable u usporedbi HTAP vs IM (H3).
--
-- U glavnom eksperimentu IM koristi OPTION(MAXDOP 1) (zbog CXSYNC_PORT čekanja
-- na Hekaton tabelama), a HTAP OPTION(MAXDOP 2). Izmjereni jaz u OLTP propusnosti
-- (3,3-6,9x) time dijelom reflektira razliku u stepenu paralelizma analitičkih
-- upita, a ne isključivo dual-store arhitekturu.
--
-- Ova skripta kreira dvije dodatne "ruke" eksperimenta koje izjednačavaju MAXDOP:
--
--   ARM D2:  im.usp_OLAP_*_D2    -> IM s MAXDOP 2 (isti kao HTAP)
--   ARM D1:  htap.usp_OLAP_*_D1  -> HTAP s MAXDOP 1 (isti kao IM)
--
-- Usporedbe koje time postaju metodološki čiste:
--   HTAP (MAXDOP 2) vs IM_D2 (MAXDOP 2)   <- paralelizam izjednačen na 2
--   HTAP_D1 (MAXDOP 1) vs IM (MAXDOP 1)   <- paralelizam izjednačen na 1
--
-- Ako jaz opstaje u OBJE usporedbe, MAXDOP nije uzrok i H3 zaključak drži.
-- Razlika između (HTAP - IM_D2) i (HTAP - IM) kvantificira apsolutni doprinos
-- MAXDOP asimetrije, koji u izvornom radu nije bio izoliran.
--
-- NAPOMENA: IM s MAXDOP 2 može aktivirati CXSYNC_PORT čekanje na Hekaton
-- tabelama. To NIJE greška mjerenja nego mjereni ishod - skripta 11 bilježi
-- wait statistiku pa se taj efekt kvantificira umjesto da se izbjegava.
--
-- Preduslov: 07_StoredProcs_OLAP.sql, 07b_..., 09_Fix_OLAP_MaxDop.sql
-- Trajanje:  < 1 s (samo DDL)
-- =============================================================================

USE HTAPBenchmark;
GO

-- =============================================================================
-- ARM D2: im.* analitika s MAXDOP 2 (izjednačeno s HTAP)
-- =============================================================================

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity_D2 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors_D2 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution_D2 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer_D2 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity_D2 AS BEGIN
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
-- ARM D1: htap.* analitika s MAXDOP 1 (izjednačeno s IM)
-- Čita cs.* tabele - identično kao produkcijska htap.* analitika.
-- =============================================================================

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity_D1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors_D1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution_D1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer_D1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity_D1 AS BEGIN
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

PRINT 'MAXDOP control arms created: im.usp_OLAP_*_D2 (MAXDOP 2), htap.usp_OLAP_*_D1 (MAXDOP 1).';
GO
