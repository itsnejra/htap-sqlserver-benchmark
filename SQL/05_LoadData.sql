-- =============================================================================
-- HTAPBenchmark: 05_LoadData.sql
-- Učitavanje podataka iz StackOverflow2010 u sve 4 konfiguracije
-- PREDUVJET: Baza StackOverflow2010 mora biti dostupna na istom SQL Server instanceu
-- NAPOMENA: Ovaj proces može trajati 30-120 minuta ovisno o hardware-u
-- =============================================================================

USE HTAPBenchmark;
GO

SET NOCOUNT ON;
PRINT CONCAT('Početak učitavanja: ', CONVERT(NVARCHAR, GETDATE(), 120));
GO

-- ============================================================
-- KORAK 1: BASELINE shema (disk-based, najbrže učitavanje)
-- ============================================================
PRINT '';
PRINT '=== [1/4] BASELINE shema ===';

INSERT INTO baseline.Users WITH (TABLOCK)
    (Id, Reputation, CreationDate, DisplayName, LastAccessDate,
     WebsiteUrl, Location, AboutMe, Views, UpVotes, DownVotes, Age, AccountId)
SELECT
    Id,
    ISNULL(Reputation, 1),
    CreationDate,
    DisplayName,
    LastAccessDate,
    WebsiteUrl,
    Location,
    AboutMe,
    ISNULL(Views, 0),
    ISNULL(UpVotes, 0),
    ISNULL(DownVotes, 0),
    Age,
    AccountId
FROM StackOverflow2010.dbo.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO baseline.Posts WITH (TABLOCK)
    (Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate, Score,
     ViewCount, Body, OwnerUserId, LastEditorUserId, LastEditorDisplayName,
     LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
     Title, Tags, AnswerCount, CommentCount, FavoriteCount)
SELECT
    Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate,
    ISNULL(Score, 0),
    ISNULL(ViewCount, 0),
    Body, OwnerUserId, LastEditorUserId, LastEditorDisplayName,
    LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
    Title, Tags,
    ISNULL(AnswerCount, 0),
    ISNULL(CommentCount, 0),
    ISNULL(FavoriteCount, 0)
FROM StackOverflow2010.dbo.Posts WITH (NOLOCK);
PRINT CONCAT('  Posts:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO baseline.Comments WITH (TABLOCK)
    (Id, PostId, Score, Text, CreationDate, UserId)
SELECT Id, PostId, ISNULL(Score, 0), Text, CreationDate, UserId
FROM StackOverflow2010.dbo.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO baseline.Votes WITH (TABLOCK)
    (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount)
SELECT Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount
FROM StackOverflow2010.dbo.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO baseline.Badges WITH (TABLOCK)
    (Id, UserId, Name, Date)
SELECT Id, UserId, Name, Date
FROM StackOverflow2010.dbo.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');
GO

-- ============================================================
-- KORAK 2: CS shema (kopija iz baseline, efikasno)
-- ============================================================
PRINT '';
PRINT '=== [2/4] CS shema ===';

INSERT INTO cs.Users WITH (TABLOCK)
SELECT * FROM baseline.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO cs.Posts WITH (TABLOCK)
SELECT * FROM baseline.Posts WITH (NOLOCK);
PRINT CONCAT('  Posts:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO cs.Comments WITH (TABLOCK)
SELECT * FROM baseline.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO cs.Votes WITH (TABLOCK)
SELECT * FROM baseline.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO cs.Badges WITH (TABLOCK)
SELECT * FROM baseline.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');
GO

-- ============================================================
-- KORAK 3: IM shema (memory-optimized, ne podržava TABLOCK)
-- Preporučuje se batch INSERT u petlji za veće tablice
-- ============================================================
PRINT '';
PRINT '=== [3/4] IM shema (memory-optimized) ===';

-- Users - direktno (manji dataset)
INSERT INTO im.Users
    (Id, Reputation, CreationDate, DisplayName, LastAccessDate,
     WebsiteUrl, Location, AboutMe, Views, UpVotes, DownVotes, Age, AccountId)
SELECT * FROM baseline.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

-- Posts za IM: Body = NULL da se uštedi RAM (~10 GB po konfiguraciji)
-- Body nije korišten ni u jednom OLTP/OLAP upitu u benchmarku
-- Ovo omogućava punjenje punog dataseta u memoriji na 32 GB sistemu
INSERT INTO im.Posts
    (Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate, Score,
     ViewCount, Body, OwnerUserId, LastEditorUserId, LastEditorDisplayName,
     LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
     Title, Tags, AnswerCount, CommentCount, FavoriteCount)
SELECT
    Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate, Score,
    ViewCount,
    NULL,  -- Body = NULL u in-memory konfiguracijama (RAM optimizacija)
    OwnerUserId, LastEditorUserId, LastEditorDisplayName,
    LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
    Title, Tags, AnswerCount, CommentCount, FavoriteCount
FROM baseline.Posts WITH (NOLOCK);
DECLARE @TotalPosts BIGINT = @@ROWCOUNT;
PRINT CONCAT('  Posts:    ', FORMAT(@TotalPosts, 'N0'), ' redova (Body=NULL, RAM optimizacija)');

INSERT INTO im.Comments (Id, PostId, Score, Text, CreationDate, UserId)
SELECT * FROM baseline.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO im.Votes (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount)
SELECT * FROM baseline.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO im.Badges (Id, UserId, Name, Date)
SELECT * FROM baseline.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');
GO

-- ============================================================
-- KORAK 4: HTAP shema (identično kao IM)
-- ============================================================
PRINT '';
PRINT '=== [4/4] HTAP shema (memory-optimized + columnstore) ===';

INSERT INTO htap.Users
    (Id, Reputation, CreationDate, DisplayName, LastAccessDate,
     WebsiteUrl, Location, AboutMe, Views, UpVotes, DownVotes, Age, AccountId)
SELECT * FROM baseline.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO htap.Posts
    (Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate, Score,
     ViewCount, Body, OwnerUserId, LastEditorUserId, LastEditorDisplayName,
     LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
     Title, Tags, AnswerCount, CommentCount, FavoriteCount)
SELECT
    Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate, Score,
    ViewCount,
    NULL,  -- Body = NULL u in-memory konfiguracijama (RAM optimizacija)
    OwnerUserId, LastEditorUserId, LastEditorDisplayName,
    LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
    Title, Tags, AnswerCount, CommentCount, FavoriteCount
FROM baseline.Posts WITH (NOLOCK);
DECLARE @TotalHTAP BIGINT = @@ROWCOUNT;
PRINT CONCAT('  Posts:    ', FORMAT(@TotalHTAP, 'N0'), ' redova (Body=NULL, RAM optimizacija)');

INSERT INTO htap.Comments (Id, PostId, Score, Text, CreationDate, UserId)
SELECT * FROM baseline.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO htap.Votes (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount)
SELECT * FROM baseline.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');

INSERT INTO htap.Badges (Id, UserId, Name, Date)
SELECT * FROM baseline.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT, 'N0'), ' redova');
GO

-- ============================================================
-- KORAK 5: Kompresija columnstore row groups za CS shemu
-- ============================================================
PRINT '';
PRINT '=== Kompresija columnstore (CS shema) ===';
ALTER INDEX NCSI_cs_Posts     ON cs.Posts     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
PRINT '  cs.Posts done';
ALTER INDEX NCSI_cs_Comments  ON cs.Comments  REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
PRINT '  cs.Comments done';
ALTER INDEX NCSI_cs_Votes     ON cs.Votes     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
PRINT '  cs.Votes done';
ALTER INDEX NCSI_cs_Users     ON cs.Users     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
PRINT '  cs.Users done';
ALTER INDEX NCSI_cs_Badges    ON cs.Badges    REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
PRINT '  cs.Badges done';
GO

-- ============================================================
-- KORAK 6: Provjera broja redova po shemi
-- ============================================================
PRINT '';
PRINT '=== Validacija broja redova ===';
SELECT
    s.name          AS [Shema],
    t.name          AS [Tablica],
    SUM(p.rows)     AS [BrojRedova]
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
WHERE s.name IN ('baseline', 'cs', 'im', 'htap')
GROUP BY s.name, t.name
ORDER BY s.name, t.name;

PRINT '';
PRINT CONCAT('Učitavanje završeno: ', CONVERT(NVARCHAR, GETDATE(), 120));
GO
