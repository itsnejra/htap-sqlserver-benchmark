-- =============================================================================
-- HTAPBenchmark: 12_VerifyDataIntegrity.sql
--
-- SVRHA: provjeriti da sve četiri sheme sadrže pun skup podataka prije mjerenja.
--
-- ZAŠTO: im.* i htap.* tablice su DURABILITY = SCHEMA_ONLY i gube SVE podatke pri
--        svakom restartu SQL Servera. Ako se 05b_LoadData_CS_HTAP_Only.sql ne
--        pokrene nakon restarta, benchmark radi nad djelimično praznim tablicama i
--        uredno proizvodi rezultate — samo neuporedive s ostatkom eksperimenta.
--        Manje redova znači kraće OLAP skeniranje, pa i OLTP i OLAP izgledaju
--        višestruko brži nego što jesu.
--
-- KADA: nakon svakog restarta SQL Servera ili mašine, prije pokretanja bilo koje
--       mjerne sesije. Benchmark aplikacija radi istu provjeru automatski, ali ovo
--       je brže nego čekati da se pokrene.
--
-- Trajanje: nekoliko sekundi (COUNT_BIG nad memorijskim tablicama je brz).
-- =============================================================================

USE HTAPBenchmark;
GO

SET NOCOUNT ON;

DECLARE @ocekivano TABLE (Tablica SYSNAME PRIMARY KEY, Redova BIGINT);
INSERT INTO @ocekivano (Tablica, Redova) VALUES
    ('Posts',     3729195),
    ('Users',      299398),
    ('Votes',    10143364),
    ('Comments',  3875183),
    ('Badges',    1102019);

DECLARE @stvarno TABLE (Shema SYSNAME, Tablica SYSNAME, Redova BIGINT);

-- MAXDOP 1: paralelni planovi nad memorijsko-optimiziranim tablicama izazivaju
-- CXSYNC_PORT čekanje.
INSERT INTO @stvarno (Shema, Tablica, Redova)
SELECT 'baseline', 'Posts',    COUNT_BIG(*) FROM baseline.Posts    UNION ALL
SELECT 'baseline', 'Users',    COUNT_BIG(*) FROM baseline.Users    UNION ALL
SELECT 'baseline', 'Votes',    COUNT_BIG(*) FROM baseline.Votes    UNION ALL
SELECT 'baseline', 'Comments', COUNT_BIG(*) FROM baseline.Comments UNION ALL
SELECT 'baseline', 'Badges',   COUNT_BIG(*) FROM baseline.Badges   UNION ALL
SELECT 'cs',       'Posts',    COUNT_BIG(*) FROM cs.Posts          UNION ALL
SELECT 'cs',       'Users',    COUNT_BIG(*) FROM cs.Users          UNION ALL
SELECT 'cs',       'Votes',    COUNT_BIG(*) FROM cs.Votes          UNION ALL
SELECT 'cs',       'Comments', COUNT_BIG(*) FROM cs.Comments       UNION ALL
SELECT 'cs',       'Badges',   COUNT_BIG(*) FROM cs.Badges         UNION ALL
SELECT 'im',       'Posts',    COUNT_BIG(*) FROM im.Posts          UNION ALL
SELECT 'im',       'Users',    COUNT_BIG(*) FROM im.Users          UNION ALL
SELECT 'im',       'Votes',    COUNT_BIG(*) FROM im.Votes          UNION ALL
SELECT 'im',       'Comments', COUNT_BIG(*) FROM im.Comments       UNION ALL
SELECT 'im',       'Badges',   COUNT_BIG(*) FROM im.Badges         UNION ALL
SELECT 'htap',     'Posts',    COUNT_BIG(*) FROM htap.Posts        UNION ALL
SELECT 'htap',     'Users',    COUNT_BIG(*) FROM htap.Users        UNION ALL
SELECT 'htap',     'Votes',    COUNT_BIG(*) FROM htap.Votes        UNION ALL
SELECT 'htap',     'Comments', COUNT_BIG(*) FROM htap.Comments     UNION ALL
SELECT 'htap',     'Badges',   COUNT_BIG(*) FROM htap.Badges
OPTION (MAXDOP 1);

-- Tolerancija 5 %: benchmark tokom rada dodaje glasove i komentare, a cleanup ih
-- briše po vodenom žigu, pa mala odstupanja nisu problem. Prag hvata razliku reda
-- veličine, ne šum.
SELECT
    s.Shema,
    s.Tablica,
    Redova        = s.Redova,
    Ocekivano     = o.Redova,
    PostoOcekivanog = CAST(100.0 * s.Redova / NULLIF(o.Redova, 0) AS DECIMAL(6,1)),
    Status        = CASE
                        WHEN ABS(1.0 * s.Redova / NULLIF(o.Redova, 0) - 1.0) <= 0.05 THEN 'OK'
                        WHEN s.Redova = 0 THEN 'PRAZNO'
                        ELSE 'ODSTUPANJE'
                    END
FROM @stvarno s
INNER JOIN @ocekivano o ON o.Tablica = s.Tablica
ORDER BY
    CASE s.Shema WHEN 'baseline' THEN 1 WHEN 'cs' THEN 2 WHEN 'im' THEN 3 ELSE 4 END,
    s.Tablica;

-- Zbirni zaključak
DECLARE @problema INT = (
    SELECT COUNT(*)
    FROM @stvarno s
    INNER JOIN @ocekivano o ON o.Tablica = s.Tablica
    WHERE ABS(1.0 * s.Redova / NULLIF(o.Redova, 0) - 1.0) > 0.05
);

IF @problema = 0
    PRINT 'SVE SHEME POTPUNE — mjerenje moze poceti.';
ELSE
BEGIN
    PRINT '=============================================================';
    PRINT 'UPOZORENJE: ' + CAST(@problema AS VARCHAR(10)) + ' tablica odstupa od ocekivanog broja redova.';
    PRINT '';
    PRINT 'Za im.* i htap.*  -> pokrenite SQL/05b_LoadData_CS_HTAP_Only.sql';
    PRINT 'Za baseline i cs  -> pokrenite SQL/05_LoadData.sql';
    PRINT '';
    PRINT 'NE pokrecite mjerenje dok se ovo ne rijesi: rezultati nece biti';
    PRINT 'usporedivi s ostatkom eksperimenta.';
    PRINT '=============================================================';
END
GO
