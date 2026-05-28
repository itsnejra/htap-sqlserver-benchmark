-- Brzo učitavanje samo cs i htap shema (baseline kao intermedijar)
-- htap.Votes i htap.Comments: TOP 500K da se spriječi OOM pri C=16/32
USE HTAPBenchmark;
SET NOCOUNT ON;
PRINT CONCAT('Start: ', CONVERT(NVARCHAR, GETDATE(), 120));
GO

PRINT '=== [1/3] BASELINE (intermedijar) ===';
INSERT INTO baseline.Users WITH (TABLOCK)
    (Id,Reputation,CreationDate,DisplayName,LastAccessDate,WebsiteUrl,Location,AboutMe,Views,UpVotes,DownVotes,Age,AccountId)
SELECT Id,ISNULL(Reputation,1),CreationDate,DisplayName,LastAccessDate,WebsiteUrl,Location,AboutMe,
    ISNULL(Views,0),ISNULL(UpVotes,0),ISNULL(DownVotes,0),Age,AccountId
FROM StackOverflow2010.dbo.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT,'N0'));

INSERT INTO baseline.Posts WITH (TABLOCK)
    (Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,Score,ViewCount,Body,OwnerUserId,
     LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,CommunityOwnedDate,
     ClosedDate,Title,Tags,AnswerCount,CommentCount,FavoriteCount)
SELECT Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,ISNULL(Score,0),ISNULL(ViewCount,0),
    Body,OwnerUserId,LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,
    CommunityOwnedDate,ClosedDate,Title,Tags,ISNULL(AnswerCount,0),ISNULL(CommentCount,0),ISNULL(FavoriteCount,0)
FROM StackOverflow2010.dbo.Posts WITH (NOLOCK);
PRINT CONCAT('  Posts:    ', FORMAT(@@ROWCOUNT,'N0'));

INSERT INTO baseline.Comments WITH (TABLOCK) (Id,PostId,Score,Text,CreationDate,UserId)
SELECT Id,PostId,ISNULL(Score,0),Text,CreationDate,UserId FROM StackOverflow2010.dbo.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT,'N0'));

INSERT INTO baseline.Votes WITH (TABLOCK) (Id,PostId,VoteTypeId,CreationDate,UserId,BountyAmount)
SELECT Id,PostId,VoteTypeId,CreationDate,UserId,BountyAmount FROM StackOverflow2010.dbo.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT,'N0'));

INSERT INTO baseline.Badges WITH (TABLOCK) (Id,UserId,Name,Date)
SELECT Id,UserId,Name,Date FROM StackOverflow2010.dbo.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT,'N0'));
GO

PRINT '=== [2/3] CS shema ===';
INSERT INTO cs.Users WITH (TABLOCK) SELECT * FROM baseline.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT,'N0'));
INSERT INTO cs.Posts WITH (TABLOCK) SELECT * FROM baseline.Posts WITH (NOLOCK);
PRINT CONCAT('  Posts:    ', FORMAT(@@ROWCOUNT,'N0'));
INSERT INTO cs.Comments WITH (TABLOCK) SELECT * FROM baseline.Comments WITH (NOLOCK);
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT,'N0'));
INSERT INTO cs.Votes WITH (TABLOCK) SELECT * FROM baseline.Votes WITH (NOLOCK);
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT,'N0'));
INSERT INTO cs.Badges WITH (TABLOCK) SELECT * FROM baseline.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT,'N0'));
GO

PRINT '=== [3/3] HTAP shema (SCHEMA_ONLY, TOP 500K za Votes/Comments) ===';
INSERT INTO htap.Users
    (Id,Reputation,CreationDate,DisplayName,LastAccessDate,WebsiteUrl,Location,AboutMe,Views,UpVotes,DownVotes,Age,AccountId)
SELECT * FROM baseline.Users WITH (NOLOCK);
PRINT CONCAT('  Users:    ', FORMAT(@@ROWCOUNT,'N0'));

INSERT INTO htap.Posts
    (Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,Score,ViewCount,Body,OwnerUserId,
     LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,CommunityOwnedDate,
     ClosedDate,Title,Tags,AnswerCount,CommentCount,FavoriteCount)
SELECT Id,PostTypeId,ParentId,AcceptedAnswerId,CreationDate,Score,ViewCount,
    NULL, -- Body=NULL (RAM optimizacija za in-memory tablice)
    OwnerUserId,LastEditorUserId,LastEditorDisplayName,LastEditDate,LastActivityDate,
    CommunityOwnedDate,ClosedDate,Title,Tags,AnswerCount,CommentCount,FavoriteCount
FROM baseline.Posts WITH (NOLOCK);
PRINT CONCAT('  Posts:    ', FORMAT(@@ROWCOUNT,'N0'));

-- TOP 500K: sprjecava OOM version chain akumulaciju pri C=16/32
INSERT INTO htap.Comments (Id,PostId,Score,Text,CreationDate,UserId)
SELECT TOP 500000 Id,PostId,Score,Text,CreationDate,UserId
FROM baseline.Comments WITH (NOLOCK) ORDER BY Id;
PRINT CONCAT('  Comments: ', FORMAT(@@ROWCOUNT,'N0'), ' (TOP 500K)');

INSERT INTO htap.Votes (Id,PostId,VoteTypeId,CreationDate,UserId,BountyAmount)
SELECT TOP 500000 Id,PostId,VoteTypeId,CreationDate,UserId,BountyAmount
FROM baseline.Votes WITH (NOLOCK) ORDER BY Id;
PRINT CONCAT('  Votes:    ', FORMAT(@@ROWCOUNT,'N0'), ' (TOP 500K)');

INSERT INTO htap.Badges (Id,UserId,Name,Date)
SELECT Id,UserId,Name,Date FROM baseline.Badges WITH (NOLOCK);
PRINT CONCAT('  Badges:   ', FORMAT(@@ROWCOUNT,'N0'));
GO

PRINT '=== Kompresija columnstore (cs shema) ===';
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

PRINT '';
SELECT s.name AS Shema, t.name AS Tablica, SUM(p.rows) AS Redovi
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
WHERE s.name IN ('baseline','cs','htap')
GROUP BY s.name, t.name ORDER BY s.name, t.name;
PRINT CONCAT('Gotovo: ', CONVERT(NVARCHAR, GETDATE(), 120));
GO
