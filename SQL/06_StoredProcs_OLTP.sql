-- =============================================================================
-- HTAPBenchmark: 06_StoredProcs_OLTP.sql
-- OLTP stored procedure za sve 4 konfiguracije
-- Operacije:
--   1. usp_GetPostById         - point lookup po PK (10% workload-a)
--   2. usp_GetUserById         - point lookup korisnika (5%)
--   3. usp_InsertVote          - INSERT glasanja (35%)
--   4. usp_UpdatePostScore     - UPDATE score postova (25%)
--   5. usp_InsertComment       - INSERT komentara (15%)
--   6. usp_GetRecentUserPosts  - range scan (10%)
--
-- IM i HTAP sheme koriste NATIVELY COMPILED procedure za maksimalne performanse
-- =============================================================================

USE HTAPBenchmark;
GO

-- ===========================================================================
-- BASELINE stored procedures (regular T-SQL)
-- ===========================================================================

CREATE OR ALTER PROCEDURE baseline.usp_GetPostById
    @PostId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId,
           Title, Tags, AnswerCount, CommentCount, FavoriteCount, AcceptedAnswerId
    FROM baseline.Posts
    WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE baseline.usp_GetUserById
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, DisplayName, Reputation, CreationDate, LastAccessDate,
           Views, UpVotes, DownVotes, Location
    FROM baseline.Users
    WHERE Id = @UserId;
END;
GO

CREATE OR ALTER PROCEDURE baseline.usp_InsertVote
    @Id          INT,
    @PostId      INT,
    @VoteTypeId  TINYINT,
    @CreationDate DATE,
    @UserId      INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO baseline.Votes (Id, PostId, VoteTypeId, CreationDate, UserId)
    VALUES (@Id, @PostId, @VoteTypeId, @CreationDate, @UserId);
    -- Ažuriranje Score (1=UpVote, 2=DownVote, 3=Favorite)
    IF @VoteTypeId = 1
        UPDATE baseline.Posts SET Score = Score + 1 WHERE Id = @PostId;
    ELSE IF @VoteTypeId = 2
        UPDATE baseline.Posts SET Score = Score - 1 WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE baseline.usp_UpdatePostScore
    @PostId INT,
    @Delta  INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE baseline.Posts SET Score = Score + @Delta WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE baseline.usp_InsertComment
    @Id          INT,
    @PostId      INT,
    @Score       INT,
    @Text        NVARCHAR(700),
    @CreationDate DATETIME2(0),
    @UserId      INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO baseline.Comments (Id, PostId, Score, Text, CreationDate, UserId)
    VALUES (@Id, @PostId, @Score, @Text, @CreationDate, @UserId);
    UPDATE baseline.Posts SET CommentCount = CommentCount + 1 WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE baseline.usp_GetRecentUserPosts
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP 10 Id, PostTypeId, CreationDate, Score, Title, AnswerCount, CommentCount
    FROM baseline.Posts
    WHERE OwnerUserId = @UserId
    ORDER BY CreationDate DESC;
END;
GO

-- ===========================================================================
-- CS stored procedures (identično kao baseline, samo druga shema)
-- ===========================================================================

CREATE OR ALTER PROCEDURE cs.usp_GetPostById
    @PostId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId,
           Title, Tags, AnswerCount, CommentCount, FavoriteCount, AcceptedAnswerId
    FROM cs.Posts
    WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_GetUserById
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, DisplayName, Reputation, CreationDate, LastAccessDate,
           Views, UpVotes, DownVotes, Location
    FROM cs.Users
    WHERE Id = @UserId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_InsertVote
    @Id          INT,
    @PostId      INT,
    @VoteTypeId  TINYINT,
    @CreationDate DATE,
    @UserId      INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO cs.Votes (Id, PostId, VoteTypeId, CreationDate, UserId)
    VALUES (@Id, @PostId, @VoteTypeId, @CreationDate, @UserId);
    IF @VoteTypeId = 1
        UPDATE cs.Posts SET Score = Score + 1 WHERE Id = @PostId;
    ELSE IF @VoteTypeId = 2
        UPDATE cs.Posts SET Score = Score - 1 WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_UpdatePostScore
    @PostId INT,
    @Delta  INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE cs.Posts SET Score = Score + @Delta WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_InsertComment
    @Id          INT,
    @PostId      INT,
    @Score       INT,
    @Text        NVARCHAR(700),
    @CreationDate DATETIME2(0),
    @UserId      INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO cs.Comments (Id, PostId, Score, Text, CreationDate, UserId)
    VALUES (@Id, @PostId, @Score, @Text, @CreationDate, @UserId);
    UPDATE cs.Posts SET CommentCount = CommentCount + 1 WHERE Id = @PostId;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_GetRecentUserPosts
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP 10 Id, PostTypeId, CreationDate, Score, Title, AnswerCount, CommentCount
    FROM cs.Posts
    WHERE OwnerUserId = @UserId
    ORDER BY CreationDate DESC;
END;
GO

-- ===========================================================================
-- IM - Natively Compiled stored procedures
-- ZAHTJEV: Mogu pristupiti SAMO memory-optimized tablicama (im.*)
-- ZAHTJEV: Moraju koristiti ATOMIC blok
-- ===========================================================================

-- im: GetPostById (natively compiled)
IF OBJECT_ID('im.usp_GetPostById', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_GetPostById;
GO
CREATE PROCEDURE im.usp_GetPostById
    @PostId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId,
           Title, Tags, AnswerCount, CommentCount, FavoriteCount, AcceptedAnswerId
    FROM im.Posts
    WHERE Id = @PostId;
END;
GO

-- im: GetUserById (natively compiled)
IF OBJECT_ID('im.usp_GetUserById', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_GetUserById;
GO
CREATE PROCEDURE im.usp_GetUserById
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT Id, DisplayName, Reputation, CreationDate, LastAccessDate,
           Views, UpVotes, DownVotes, Location
    FROM im.Users
    WHERE Id = @UserId;
END;
GO

-- im: InsertVote (natively compiled)
IF OBJECT_ID('im.usp_InsertVote', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_InsertVote;
GO
CREATE PROCEDURE im.usp_InsertVote
    @Id          INT,
    @PostId      INT,
    @VoteTypeId  TINYINT,
    @CreationDate DATE,
    @UserId      INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    INSERT INTO im.Votes (Id, PostId, VoteTypeId, CreationDate, UserId)
    VALUES (@Id, @PostId, @VoteTypeId, @CreationDate, @UserId);

    IF @VoteTypeId = 1
        UPDATE im.Posts SET Score = Score + 1 WHERE Id = @PostId;
    ELSE IF @VoteTypeId = 2
        UPDATE im.Posts SET Score = Score - 1 WHERE Id = @PostId;
END;
GO

-- im: UpdatePostScore (natively compiled)
IF OBJECT_ID('im.usp_UpdatePostScore', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_UpdatePostScore;
GO
CREATE PROCEDURE im.usp_UpdatePostScore
    @PostId INT,
    @Delta  INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    UPDATE im.Posts SET Score = Score + @Delta WHERE Id = @PostId;
END;
GO

-- im: InsertComment (natively compiled)
IF OBJECT_ID('im.usp_InsertComment', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_InsertComment;
GO
CREATE PROCEDURE im.usp_InsertComment
    @Id           INT,
    @PostId       INT,
    @Score        INT,
    @Text         NVARCHAR(700),
    @CreationDate DATETIME2(0),
    @UserId       INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    INSERT INTO im.Comments (Id, PostId, Score, Text, CreationDate, UserId)
    VALUES (@Id, @PostId, @Score, @Text, @CreationDate, @UserId);
    UPDATE im.Posts SET CommentCount = CommentCount + 1 WHERE Id = @PostId;
END;
GO

-- im: GetRecentUserPosts (natively compiled)
IF OBJECT_ID('im.usp_GetRecentUserPosts', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_GetRecentUserPosts;
GO
CREATE PROCEDURE im.usp_GetRecentUserPosts
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT TOP (10) Id, PostTypeId, CreationDate, Score, Title, AnswerCount, CommentCount
    FROM im.Posts
    WHERE OwnerUserId = @UserId
    ORDER BY CreationDate DESC;
END;
GO

-- ===========================================================================
-- HTAP - Natively Compiled stored procedures (identično kao IM, druga shema)
-- ===========================================================================

IF OBJECT_ID('htap.usp_GetPostById', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_GetPostById;
GO
CREATE PROCEDURE htap.usp_GetPostById
    @PostId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId,
           Title, Tags, AnswerCount, CommentCount, FavoriteCount, AcceptedAnswerId
    FROM htap.Posts
    WHERE Id = @PostId;
END;
GO

IF OBJECT_ID('htap.usp_GetUserById', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_GetUserById;
GO
CREATE PROCEDURE htap.usp_GetUserById
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT Id, DisplayName, Reputation, CreationDate, LastAccessDate,
           Views, UpVotes, DownVotes, Location
    FROM htap.Users
    WHERE Id = @UserId;
END;
GO

IF OBJECT_ID('htap.usp_InsertVote', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_InsertVote;
GO
CREATE PROCEDURE htap.usp_InsertVote
    @Id          INT,
    @PostId      INT,
    @VoteTypeId  TINYINT,
    @CreationDate DATE,
    @UserId      INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    INSERT INTO htap.Votes (Id, PostId, VoteTypeId, CreationDate, UserId)
    VALUES (@Id, @PostId, @VoteTypeId, @CreationDate, @UserId);

    IF @VoteTypeId = 1
        UPDATE htap.Posts SET Score = Score + 1 WHERE Id = @PostId;
    ELSE IF @VoteTypeId = 2
        UPDATE htap.Posts SET Score = Score - 1 WHERE Id = @PostId;
END;
GO

IF OBJECT_ID('htap.usp_UpdatePostScore', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_UpdatePostScore;
GO
CREATE PROCEDURE htap.usp_UpdatePostScore
    @PostId INT,
    @Delta  INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    UPDATE htap.Posts SET Score = Score + @Delta WHERE Id = @PostId;
END;
GO

IF OBJECT_ID('htap.usp_InsertComment', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_InsertComment;
GO
CREATE PROCEDURE htap.usp_InsertComment
    @Id           INT,
    @PostId       INT,
    @Score        INT,
    @Text         NVARCHAR(700),
    @CreationDate DATETIME2(0),
    @UserId       INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    INSERT INTO htap.Comments (Id, PostId, Score, Text, CreationDate, UserId)
    VALUES (@Id, @PostId, @Score, @Text, @CreationDate, @UserId);
    UPDATE htap.Posts SET CommentCount = CommentCount + 1 WHERE Id = @PostId;
END;
GO

IF OBJECT_ID('htap.usp_GetRecentUserPosts', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_GetRecentUserPosts;
GO
CREATE PROCEDURE htap.usp_GetRecentUserPosts
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    SELECT TOP (10) Id, PostTypeId, CreationDate, Score, Title, AnswerCount, CommentCount
    FROM htap.Posts
    WHERE OwnerUserId = @UserId
    ORDER BY CreationDate DESC;
END;
GO

PRINT 'OLTP stored procedure za sve 4 konfiguracije uspješno kreirane.';
GO
