-- =============================================================================
-- HTAPBenchmark: 07b_StoredProcs_OLAP_HTAP_DualStore.sql
-- HTAP OLAP procedure - dual-store arhitektura
--
-- HTAP konfiguracija koristi dual-store pristup:
--   - OLTP operacije: htap.* (memory-optimized tablice)
--   - OLAP operacije: cs.* (disk-based columnstore tablice)
--
-- Ovo odgovara arhitekturama komercijalnih HTAP sistema:
--   - TiDB: TiKV (OLTP) + TiFlash (OLAP/columnstore)
--   - F1 Lightning: F1 (OLTP) + BigQuery (analytics)
--   - SQL Server 2022: In-Memory OLTP + Columnstore analytics layer
--
-- Prednost: OLAP čitanje ne interferira s OLTP pisanjem jer koriste
--           različite storage mehanizme i lock-free read putanje.
-- =============================================================================

USE HTAPBenchmark;
GO

-- NAPOMENA: htap OLAP procedure čitaju iz cs.* tablice
-- koje su učitane identičnim podacima (isti snapshot dataseta)
-- Ovo reprezentira HTAP analitički sloj koji se ažurira asinkrono

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
    FROM cs.Posts   -- HTAP dual-store: OLAP čita columnstore layer
    GROUP BY YEAR(CreationDate), MONTH(CreationDate), PostTypeId
    ORDER BY Godina, Mjesec, PostTypeId;
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
    FROM cs.Users  u   -- HTAP dual-store: OLAP čita columnstore layer
    INNER JOIN cs.Posts p ON p.OwnerUserId = u.Id AND p.PostTypeId = 2
    GROUP BY u.Id, u.DisplayName, u.Reputation
    ORDER BY BrojOdgovora DESC;
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
    FROM cs.Votes v   -- HTAP dual-store: OLAP čita columnstore layer
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
    FROM cs.Posts q   -- HTAP dual-store: OLAP čita columnstore layer
    LEFT JOIN cs.Posts a
        ON a.Id = q.AcceptedAnswerId AND a.PostTypeId = 2
    WHERE q.PostTypeId = 1
    GROUP BY YEAR(q.CreationDate), MONTH(q.CreationDate)
    ORDER BY Godina, Mjesec;
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
        FROM cs.Posts   -- HTAP dual-store: OLAP čita columnstore layer
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

PRINT 'HTAP OLAP dual-store procedure uspješno kreirane (OLAP -> cs.* columnstore layer).';
GO
