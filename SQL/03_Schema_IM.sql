-- =============================================================================
-- HTAPBenchmark: 03_Schema_IM.sql
-- Konfiguracija 3: IM (In-Memory OLTP)
-- Memorijski optimizirane tablice (Hekaton engine)
-- NAPOMENA: Bez columnstore - čista OLTP optimizacija
--
-- BUCKET_COUNT preporuka: 1-2x broj očekivanih redova (power-of-2)
--   Users    ~171K  -> 262144  (256K)
--   Posts    ~3.8M  -> 4194304 (4M)
--   Comments ~2.6M  -> 4194304 (4M)
--   Votes    ~8.4M  -> 16777216 (16M)
--   Badges   ~251K  -> 524288  (512K)
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================
-- im.Users (Memory-Optimized, DURABILITY = SCHEMA_AND_DATA)
-- ============================================================
CREATE TABLE im.Users (
    Id               INT            NOT NULL,
    Reputation       INT            NOT NULL
        CONSTRAINT DF_im_Users_Reputation DEFAULT 1,
    CreationDate     DATETIME2(0)   NOT NULL,
    DisplayName      NVARCHAR(40)   NOT NULL,
    LastAccessDate   DATETIME2(0)   NOT NULL,
    WebsiteUrl       NVARCHAR(200)  NULL,
    Location         NVARCHAR(100)  NULL,
    AboutMe          NVARCHAR(MAX)  NULL,
    Views            INT            NOT NULL CONSTRAINT DF_im_Users_Views DEFAULT 0,
    UpVotes          INT            NOT NULL CONSTRAINT DF_im_Users_UpVotes DEFAULT 0,
    DownVotes        INT            NOT NULL CONSTRAINT DF_im_Users_DownVotes DEFAULT 0,
    Age              INT            NULL,
    AccountId        INT            NULL,

    CONSTRAINT PK_im_Users PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 524288),   -- 299K rows -> 512K buckets
    INDEX IX_im_Users_Reputation     NONCLUSTERED (Reputation DESC, Id)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- im.Posts (Memory-Optimized)
-- ============================================================
CREATE TABLE im.Posts (
    Id                    INT            NOT NULL,
    PostTypeId            TINYINT        NOT NULL,
    ParentId              INT            NULL,
    AcceptedAnswerId      INT            NULL,
    CreationDate          DATETIME2(0)   NOT NULL,
    Score                 INT            NOT NULL CONSTRAINT DF_im_Posts_Score DEFAULT 0,
    ViewCount             INT            NOT NULL CONSTRAINT DF_im_Posts_ViewCount DEFAULT 0,
    Body                  NVARCHAR(MAX)  NULL,
    OwnerUserId           INT            NULL,
    LastEditorUserId      INT            NULL,
    LastEditorDisplayName NVARCHAR(40)   NULL,
    LastEditDate          DATETIME2(0)   NULL,
    LastActivityDate      DATETIME2(0)   NOT NULL,
    CommunityOwnedDate    DATETIME2(0)   NULL,
    ClosedDate            DATETIME2(0)   NULL,
    Title                 NVARCHAR(250)  NULL,
    Tags                  NVARCHAR(250)  NULL,
    AnswerCount           INT            NOT NULL CONSTRAINT DF_im_Posts_AnswerCount DEFAULT 0,
    CommentCount          INT            NOT NULL CONSTRAINT DF_im_Posts_CommentCount DEFAULT 0,
    FavoriteCount         INT            NOT NULL CONSTRAINT DF_im_Posts_FavoriteCount DEFAULT 0,

    CONSTRAINT PK_im_Posts PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 4194304),
    INDEX IX_im_Posts_OwnerUserId  NONCLUSTERED (OwnerUserId, CreationDate DESC),
    INDEX IX_im_Posts_CreationDate NONCLUSTERED (CreationDate DESC, PostTypeId)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- im.Comments (Memory-Optimized)
-- ============================================================
CREATE TABLE im.Comments (
    Id           INT            NOT NULL,
    PostId       INT            NOT NULL,
    Score        INT            NOT NULL CONSTRAINT DF_im_Comments_Score DEFAULT 0,
    Text         NVARCHAR(700)  NOT NULL,
    CreationDate DATETIME2(0)   NOT NULL,
    UserId       INT            NULL,

    CONSTRAINT PK_im_Comments PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 8388608),  -- 3.9M rows -> 8M buckets
    INDEX IX_im_Comments_PostId NONCLUSTERED (PostId, CreationDate)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- im.Votes (Memory-Optimized)
-- ============================================================
CREATE TABLE im.Votes (
    Id           INT      NOT NULL,
    PostId       INT      NOT NULL,
    VoteTypeId   TINYINT  NOT NULL,
    CreationDate DATE     NOT NULL,
    UserId       INT      NULL,
    BountyAmount INT      NULL,

    CONSTRAINT PK_im_Votes PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 16777216), -- 10.1M rows -> 16M buckets (1.6x, prihvatljivo)
    INDEX IX_im_Votes_PostId NONCLUSTERED (PostId, CreationDate)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- im.Badges (Memory-Optimized)
-- ============================================================
CREATE TABLE im.Badges (
    Id     INT           NOT NULL,
    UserId INT           NOT NULL,
    Name   NVARCHAR(50)  NOT NULL,
    Date   DATETIME2(0)  NOT NULL,

    CONSTRAINT PK_im_Badges PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 2097152),  -- 1.1M rows -> 2M buckets
    INDEX IX_im_Badges_UserId NONCLUSTERED (UserId, Date DESC)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

PRINT 'im shema: memorijski optimizirane tablice uspješno kreirane.';
GO
