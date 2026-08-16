-- =============================================================================
-- HTAPBenchmark: 10_H3_MaxDop_Control.sql
--
-- KONTROLNI EKSPERIMENT ZA HIPOTEZU H3
--
-- Problem: u glavnom mjerenju HTAP izvodi analitiku s OPTION (MAXDOP 2), a IM
-- s OPTION (MAXDOP 1) — jer paralelni planovi nad Hekaton tablicama izazivaju
-- CXSYNC_PORT cekanja. Razlika u stepenu paralelizma je zato confound: izmjereni
-- jaz u OLTP propusnosti (3,3-6,9x) dijelom moze poticati od paralelizma, a ne
-- iskljucivo od dual-store arhitekture.
--
-- Rjesenje: ovaj skript kreira _Dop1 varijante OLAP procedura u kojima OBJE
-- konfiguracije rade pri MAXDOP 1:
--   im.usp_OLAP_Q*_Dop1    -> cita im.*  (memorijsko-optimizirano), MAXDOP 1
--   htap.usp_OLAP_Q*_Dop1  -> cita cs.*  (disk + columnstore),      MAXDOP 1
--
-- Tijela upita su identicna onima iz 09_Fix_OLAP_MaxDop.sql; mijenja se iskljucivo
-- ime procedure i stepen paralelizma za htap. Ako HTAP i pri izjednacenom MAXDOP-u
-- zadrzi znacajnu prednost, razlika se moze pripisati fizickoj separaciji slojeva.
--
-- Pokretanje mjerenja: vidi BenchmarkApp/HTAPBenchmark.Runner/appsettings.H3Control.json
-- (OlapProcedureSuffix = "_Dop1", Configurations = [IM, HTAP], ratio 80/20).
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================================
-- im schema  - memorijsko-optimizirane tablice, MAXDOP 1 (nepromijenjeno)
-- ============================================================================
CREATE OR ALTER PROCEDURE im.usp_OLAP_Q1_MonthlyActivity_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q2_TopContributors_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q3_VoteDistribution_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q4_TimeToAnswer_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE im.usp_OLAP_Q5_UserCohortActivity_Dop1 AS BEGIN
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
-- htap schema - cita cs.* columnstore, MAXDOP 1 (spusteno s 2 radi kontrole)
-- ============================================================================
CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q1_MonthlyActivity_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q2_TopContributors_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q3_VoteDistribution_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q4_TimeToAnswer_Dop1 AS BEGIN
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

CREATE OR ALTER PROCEDURE htap.usp_OLAP_Q5_UserCohortActivity_Dop1 AS BEGIN
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

PRINT 'H3 kontrolne procedure (_Dop1) kreirane za im.* i htap.*';
GO
