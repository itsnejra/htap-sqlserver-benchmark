-- =============================================================================
-- HTAPBenchmark: 04_Schema_HTAP.sql
-- Konfiguracija 4: HTAP
-- Memorijski optimizirane tablice + Nonclustered Columnstore indeks
-- Ovo je hibridna konfiguracija: OLTP performanse + analitička podrška
-- Zahtijeva SQL Server 2016 SP1+ (preporučeno 2019)
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================
-- htap.Users (Memory-Optimized + Columnstore)
-- ============================================================
CREATE TABLE htap.Users (
    Id               INT            NOT NULL,
    Reputation       INT            NOT NULL
        CONSTRAINT DF_htap_Users_Reputation DEFAULT 1,
    CreationDate     DATETIME2(0)   NOT NULL,
    DisplayName      NVARCHAR(40)   NOT NULL,
    LastAccessDate   DATETIME2(0)   NOT NULL,
    WebsiteUrl       NVARCHAR(200)  NULL,
    Location         NVARCHAR(100)  NULL,
    AboutMe          NVARCHAR(MAX)  NULL,
    Views            INT            NOT NULL CONSTRAINT DF_htap_Users_Views DEFAULT 0,
    UpVotes          INT            NOT NULL CONSTRAINT DF_htap_Users_UpVotes DEFAULT 0,
    DownVotes        INT            NOT NULL CONSTRAINT DF_htap_Users_DownVotes DEFAULT 0,
    Age              INT            NULL,
    AccountId        INT            NULL,

    CONSTRAINT PK_htap_Users PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 524288),   -- 299K rows -> 512K buckets
    INDEX IX_htap_Users_Reputation NONCLUSTERED (Reputation DESC, Id),
    -- In-memory columnstore indeks za analitičke upite
    INDEX IX_htap_Users_CS NONCLUSTERED COLUMNSTORE
        (Id, Reputation, CreationDate, LastAccessDate, Views, UpVotes, DownVotes, Age, AccountId)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- htap.Posts (Memory-Optimized + Columnstore)
-- ============================================================
CREATE TABLE htap.Posts (
    Id                    INT            NOT NULL,
    PostTypeId            TINYINT        NOT NULL,
    ParentId              INT            NULL,
    AcceptedAnswerId      INT            NULL,
    CreationDate          DATETIME2(0)   NOT NULL,
    Score                 INT            NOT NULL CONSTRAINT DF_htap_Posts_Score DEFAULT 0,
    ViewCount             INT            NOT NULL CONSTRAINT DF_htap_Posts_ViewCount DEFAULT 0,
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
    AnswerCount           INT            NOT NULL CONSTRAINT DF_htap_Posts_AnswerCount DEFAULT 0,
    CommentCount          INT            NOT NULL CONSTRAINT DF_htap_Posts_CommentCount DEFAULT 0,
    FavoriteCount         INT            NOT NULL CONSTRAINT DF_htap_Posts_FavoriteCount DEFAULT 0,

    CONSTRAINT PK_htap_Posts PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 4194304),
    INDEX IX_htap_Posts_OwnerUserId  NONCLUSTERED (OwnerUserId, CreationDate DESC),
    INDEX IX_htap_Posts_CreationDate NONCLUSTERED (CreationDate DESC, PostTypeId),
    -- Columnstore: analitičke kolone (bez LOB Body i dužih nvarchar)
    INDEX IX_htap_Posts_CS NONCLUSTERED COLUMNSTORE (
        Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate,
        Score, ViewCount, OwnerUserId, LastEditorUserId,
        LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
        AnswerCount, CommentCount, FavoriteCount
    )
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- htap.Comments (Memory-Optimized + Columnstore)
-- ============================================================
CREATE TABLE htap.Comments (
    Id           INT            NOT NULL,
    PostId       INT            NOT NULL,
    Score        INT            NOT NULL CONSTRAINT DF_htap_Comments_Score DEFAULT 0,
    Text         NVARCHAR(700)  NOT NULL,
    CreationDate DATETIME2(0)   NOT NULL,
    UserId       INT            NULL,

    CONSTRAINT PK_htap_Comments PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 8388608),  -- 3.9M rows -> 8M buckets
    INDEX IX_htap_Comments_PostId NONCLUSTERED (PostId, CreationDate),
    INDEX IX_htap_Comments_CS NONCLUSTERED COLUMNSTORE (Id, PostId, Score, CreationDate, UserId)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- htap.Votes (Memory-Optimized + Columnstore)
-- ============================================================
CREATE TABLE htap.Votes (
    Id           INT      NOT NULL,
    PostId       INT      NOT NULL,
    VoteTypeId   TINYINT  NOT NULL,
    CreationDate DATE     NOT NULL,
    UserId       INT      NULL,
    BountyAmount INT      NULL,

    CONSTRAINT PK_htap_Votes PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 16777216), -- 10.1M rows -> 16M buckets
    INDEX IX_htap_Votes_PostId NONCLUSTERED (PostId, CreationDate),
    INDEX IX_htap_Votes_CS NONCLUSTERED COLUMNSTORE
        (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

-- ============================================================
-- htap.Badges (Memory-Optimized + Columnstore)
-- ============================================================
CREATE TABLE htap.Badges (
    Id     INT           NOT NULL,
    UserId INT           NOT NULL,
    Name   NVARCHAR(50)  NOT NULL,
    Date   DATETIME2(0)  NOT NULL,

    CONSTRAINT PK_htap_Badges PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 2097152),  -- 1.1M rows -> 2M buckets
    INDEX IX_htap_Badges_UserId NONCLUSTERED (UserId, Date DESC),
    INDEX IX_htap_Badges_CS NONCLUSTERED COLUMNSTORE (Id, UserId, Date)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);
GO

PRINT 'htap shema: memorijski optimizirane tablice s columnstore indeksima uspješno kreirane.';
GO
