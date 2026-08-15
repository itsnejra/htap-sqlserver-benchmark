-- =============================================================================
-- HTAPBenchmark: 11_DualStore_Sync.sql
--
-- SVRHA: mjerenje cijene sinhronizacije dual-store arhitekture.
--
-- PROBLEM: u glavnom eksperimentu HTAP konfiguracija fizički odvaja OLTP sloj
--          (htap.* Hekaton) od analitičkog sloja (cs.* columnstore), ali tokom
--          mjerenja NE radi nikakav mehanizam sinhronizacije. Analitički upiti
--          čitaju statičan snapshot. Produkcijski dual-store sistemi plaćaju
--          kontinuiranu cijenu propagacije: TiDB Raft replikaciju na TiFlash
--          learner čvorove, F1 Lightning Changepump i kompakciju.
--          Izmjerene prednosti HTAP-a stoga predstavljaju gornju granicu
--          ostvarivu uz nultu cijenu sinhronizacije.
--
-- RJEŠENJE: ovaj skript implementira periodičnu batch propagaciju htap.* -> cs.*
--           s podesivim intervalom. Pokretanjem benchmarka pri više intervala
--           (npr. 0 = bez sinhronizacije, 1 s, 5 s, 30 s) dobiva se krivulja
--           kompromisa između svježine analitičkih podataka i OLTP propusnosti,
--           čime tvrdnja o prednosti dual-store pristupa prestaje biti gornja
--           granica i postaje mjerena funkcija svježine.
--
-- MODEL PROPAGACIJE: benchmark generiše identifikatore iz kontinuiranog brojača,
--           pa klijent zna tačan raspon ID-ova nastalih od prošlog ciklusa.
--           Propagacija se izvodi kao seek po hash indeksu za svaki ID iz raspona
--           (O(1) po redu), a ne kao skeniranje cijele tablice. Time je cijena
--           sinhronizacije proporcionalna broju NOVIH redova, što odgovara
--           delta-store modelu iz F1 Lightning arhitekture.
--
-- MJERENJE SVJEŽINE: kašnjenje se računa nad propagiranim Comments redovima jer
--           su jedini s punom vremenskom oznakom (htap.Votes.CreationDate je tipa
--           DATE, bez vremena). Rezolucija je 1 s jer je kolona DATETIME2(0) —
--           dovoljno za intervale reda sekunde, ali ne za sub-sekundne.
--
-- Pokretanje: nakon 07b_StoredProcs_OLAP_HTAP_DualStore.sql
-- =============================================================================

USE HTAPBenchmark;
GO

-- =============================================================================
-- Pomoćne tablice
-- =============================================================================

-- Aktivni postovi iz WorkloadContext-a (~20.000 ID-ova). Puni ih benchmark
-- aplikacija na početku svakog runa; propagacija Score-a ide samo nad ovim skupom
-- jer usp_UpdatePostScore mijenja isključivo te redove.
DROP TABLE IF EXISTS htap.SyncPostIds;
GO
CREATE TABLE htap.SyncPostIds (
    Id INT NOT NULL,
    CONSTRAINT PK_htap_SyncPostIds PRIMARY KEY CLUSTERED (Id)
);
GO

-- Originalne vrijednosti Score iz cs.Posts prije bilo kakve propagacije.
-- Bez ovoga bi se izmjene akumulirale kroz runove: sinhronizacija piše u cs.Posts,
-- a WorkloadExecutor.TruncateAndReloadPostsAsync zatim učitava htap.Posts IZ
-- cs.Posts — čime bi drift ušao u polazno stanje sljedećeg runa i narušio
-- pretpostavku identičnih polaznih podataka.
DROP TABLE IF EXISTS htap.SyncPostScoreBaseline;
GO
CREATE TABLE htap.SyncPostScoreBaseline (
    Id    INT NOT NULL,
    Score INT NOT NULL,
    CONSTRAINT PK_htap_SyncPostScoreBaseline PRIMARY KEY CLUSTERED (Id)
);
GO

-- =============================================================================
-- htap.usp_SyncPrepare
-- Snima originalne Score vrijednosti aktivnih postova. Poziva se nakon što
-- benchmark napuni htap.SyncPostIds, prije prvog mjernog runa kombinacije.
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_SyncPrepare
AS
BEGIN
    SET NOCOUNT ON;

    TRUNCATE TABLE htap.SyncPostScoreBaseline;

    INSERT INTO htap.SyncPostScoreBaseline (Id, Score)
    SELECT p.Id, p.Score
    FROM cs.Posts p
    INNER JOIN htap.SyncPostIds s ON s.Id = p.Id;

    SELECT BaselineRows = COUNT(*) FROM htap.SyncPostScoreBaseline;
END;
GO

-- =============================================================================
-- htap.usp_SyncToColumnstore
-- Jedan ciklus propagacije: novi glasovi i komentari iz Hekaton sloja u
-- columnstore sloj, plus ažuriranje promijenjenih Score vrijednosti.
--
-- @FromVoteId / @ToVoteId: raspon ID-ova generisanih od prošlog ciklusa.
-- Raspon dolazi iz brojača benchmark aplikacije, pa nije potrebno skeniranje.
-- Nepostojeći ID-ovi unutar raspona (neuspjeli INSERT-i) se prirodno preskaču
-- jer je riječ o INNER JOIN-u.
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_SyncToColumnstore
    @FromVoteId         INT,
    @ToVoteId           INT,
    @FromCommentId      INT,
    @ToCommentId        INT,
    @VotesPropagated    INT   OUTPUT,
    @CommentsPropagated INT   OUTPUT,
    @PostsUpdated       INT   OUTPUT,
    @AvgLagMs           FLOAT OUTPUT,
    @MaxLagMs           FLOAT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    SET @VotesPropagated    = 0;
    SET @CommentsPropagated = 0;
    SET @PostsUpdated       = 0;
    SET @AvgLagMs           = -1;
    SET @MaxLagMs           = -1;

    -- Zaštita od runaway raspona (npr. ako klijent proslijedi pogrešan watermark).
    DECLARE @maxRange INT = 500000;

    -- -------------------------------------------------------------------------
    -- 1. Glasovi: htap.Votes -> cs.Votes
    -- -------------------------------------------------------------------------
    IF @ToVoteId >= @FromVoteId AND (@ToVoteId - @FromVoteId) < @maxRange
    BEGIN
        ;WITH IdRange AS (
            SELECT TOP (@ToVoteId - @FromVoteId + 1)
                   Id = @FromVoteId + CONVERT(INT, ROW_NUMBER() OVER (ORDER BY (SELECT NULL))) - 1
            FROM sys.all_columns a CROSS JOIN sys.all_columns b
        )
        INSERT INTO cs.Votes (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount)
        SELECT v.Id, v.PostId, v.VoteTypeId, v.CreationDate, v.UserId, v.BountyAmount
        FROM IdRange r
        INNER JOIN htap.Votes v WITH (SNAPSHOT) ON v.Id = r.Id
        -- Idempotentnost: ako je prethodni ciklus djelimično uspio (npr. glasovi
        -- prošli, komentari pali), ponovni pokušaj istog raspona ne smije pasti na
        -- narušenju primarnog ključa.
        WHERE NOT EXISTS (SELECT 1 FROM cs.Votes cv WHERE cv.Id = v.Id);

        SET @VotesPropagated = @@ROWCOUNT;
    END

    -- -------------------------------------------------------------------------
    -- 2. Komentari: htap.Comments -> cs.Comments (+ mjerenje kašnjenja svježine)
    -- -------------------------------------------------------------------------
    IF @ToCommentId >= @FromCommentId AND (@ToCommentId - @FromCommentId) < @maxRange
    BEGIN
        DECLARE @propagated TABLE (CreationDate DATETIME2(0) NOT NULL);

        ;WITH IdRange AS (
            SELECT TOP (@ToCommentId - @FromCommentId + 1)
                   Id = @FromCommentId + CONVERT(INT, ROW_NUMBER() OVER (ORDER BY (SELECT NULL))) - 1
            FROM sys.all_columns a CROSS JOIN sys.all_columns b
        )
        INSERT INTO cs.Comments (Id, PostId, Score, Text, CreationDate, UserId)
        OUTPUT inserted.CreationDate INTO @propagated (CreationDate)
        SELECT c.Id, c.PostId, c.Score, c.Text, c.CreationDate, c.UserId
        FROM IdRange r
        INNER JOIN htap.Comments c WITH (SNAPSHOT) ON c.Id = r.Id
        WHERE NOT EXISTS (SELECT 1 FROM cs.Comments cc WHERE cc.Id = c.Id);

        SET @CommentsPropagated = @@ROWCOUNT;

        IF @CommentsPropagated > 0
        BEGIN
            SELECT
                @AvgLagMs = AVG(CONVERT(FLOAT, DATEDIFF(MILLISECOND, CreationDate, @now))),
                @MaxLagMs = MAX(CONVERT(FLOAT, DATEDIFF(MILLISECOND, CreationDate, @now)))
            FROM @propagated;
        END
    END

    -- -------------------------------------------------------------------------
    -- 3. Promijenjeni Score: htap.Posts -> cs.Posts (samo aktivni skup)
    -- -------------------------------------------------------------------------
    UPDATE c
        SET c.Score = h.Score
    FROM cs.Posts c
    INNER JOIN htap.SyncPostIds s ON s.Id = c.Id
    INNER JOIN htap.Posts h WITH (SNAPSHOT) ON h.Id = s.Id
    WHERE c.Score <> h.Score;

    SET @PostsUpdated = @@ROWCOUNT;
END;
GO

-- =============================================================================
-- htap.usp_SyncCleanupColumnstore
-- Vraća cs.* sloj u polazno stanje nakon runa: briše propagirane redove i
-- restaurira originalne Score vrijednosti.
--
-- VAŽNO: bez ovoga cs.* raste kroz runove, a promijenjeni Score-ovi se preko
-- TruncateAndReloadPostsAsync vraćaju u htap.Posts, čime polazno stanje
-- sljedećeg runa prestaje biti identično — što je temeljna kontrolirana
-- varijabla eksperimentalnog dizajna.
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_SyncCleanupColumnstore
    @OriginalMaxVoteId    INT,
    @OriginalMaxCommentId INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @deleted INT = 1;

    -- Brisanje u batchevima da se izbjegne eskalacija zaključavanja i timeout.
    WHILE @deleted > 0
    BEGIN
        DELETE TOP (10000) FROM cs.Votes WHERE Id > @OriginalMaxVoteId;
        SET @deleted = @@ROWCOUNT;
    END

    SET @deleted = 1;
    WHILE @deleted > 0
    BEGIN
        DELETE TOP (10000) FROM cs.Comments WHERE Id > @OriginalMaxCommentId;
        SET @deleted = @@ROWCOUNT;
    END

    -- Restauracija Score vrijednosti iz baseline snimka.
    UPDATE c
        SET c.Score = b.Score
    FROM cs.Posts c
    INNER JOIN htap.SyncPostScoreBaseline b ON b.Id = c.Id
    WHERE c.Score <> b.Score;

    SELECT PostsRestored = @@ROWCOUNT;
END;
GO

-- =============================================================================
-- htap.usp_SyncMaintenance
-- Opcionalno: nakon završetka cijelog sync eksperimenta columnstore indeksi na
-- cs.Votes i cs.Comments nose delete bitmap i nekompresirane delta row groupe
-- od propagiranih pa obrisanih redova. Ovo ih vraća u kompresirano stanje.
-- Pokrenuti JEDNOM na kraju eksperimenta, nikako između runova (traje dugo).
-- =============================================================================
CREATE OR ALTER PROCEDURE htap.usp_SyncMaintenance
AS
BEGIN
    SET NOCOUNT ON;

    ALTER INDEX NCSI_cs_Votes    ON cs.Votes    REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
    ALTER INDEX NCSI_cs_Comments ON cs.Comments REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);

    SELECT
        Tablica       = OBJECT_NAME(rg.object_id),
        Stanje        = rg.state_desc,
        BrojGrupa     = COUNT(*),
        UkupnoRedova  = SUM(rg.total_rows),
        ObrisanihRedova = SUM(rg.deleted_rows)
    FROM sys.column_store_row_groups rg
    WHERE rg.object_id IN (OBJECT_ID('cs.Votes'), OBJECT_ID('cs.Comments'))
    GROUP BY OBJECT_NAME(rg.object_id), rg.state_desc
    ORDER BY Tablica, Stanje;
END;
GO

PRINT 'Dual-store sinhronizacija: tablice i procedure kreirane.';
PRINT '  htap.usp_SyncPrepare              - snimi baseline Score vrijednosti';
PRINT '  htap.usp_SyncToColumnstore        - jedan ciklus propagacije';
PRINT '  htap.usp_SyncCleanupColumnstore   - vrati cs.* u polazno stanje';
PRINT '  htap.usp_SyncMaintenance          - rekompresija (jednom, na kraju)';
GO
