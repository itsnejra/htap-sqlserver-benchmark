-- =============================================================================
-- HTAPBenchmark: 04b_Schema_HTAP_Fixed.sql
-- Konfiguracija 4: HTAP - Dual-Store arhitektura
--
-- SQL Server 2022 RTM (16.0.1000.6) ne podržava inline NONCLUSTERED COLUMNSTORE
-- na memory-optimized tablicama (poznato ograničenje RTM, riješeno u CU4+).
--
-- Implementacija: Dual-store HTAP arhitektura (kao TiDB/TiFlash model):
--   - htap.* tablice: memory-optimized za OLTP operacije (ista struktura kao im.*)
--   - cs.* tablice: disk-based columnstore za OLAP upite (OLAP sloj)
--
-- Ova arhitektura precizno odražava komercijalne HTAP implementacije:
--   Zhang et al. (2024): "HTAP databases typically maintain two separate
--   storage formats, one for OLTP and one for OLAP" [TKDE survey]
-- =============================================================================

USE HTAPBenchmark;
GO

-- htap.Users (identično im.Users - memory-optimized OLTP store)
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
        WITH (BUCKET_COUNT = 524288),
    INDEX IX_htap_Users_Reputation NONCLUSTERED (Reputation DESC, Id)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
GO

-- htap.Posts (identično im.Posts - memory-optimized OLTP store)
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
    INDEX IX_htap_Posts_CreationDate NONCLUSTERED (CreationDate DESC, PostTypeId)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
GO

-- htap.Comments
CREATE TABLE htap.Comments (
    Id           INT            NOT NULL,
    PostId       INT            NOT NULL,
    Score        INT            NOT NULL CONSTRAINT DF_htap_Comments_Score DEFAULT 0,
    Text         NVARCHAR(700)  NOT NULL,
    CreationDate DATETIME2(0)   NOT NULL,
    UserId       INT            NULL,
    CONSTRAINT PK_htap_Comments PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 8388608),
    INDEX IX_htap_Comments_PostId NONCLUSTERED (PostId, CreationDate)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
GO

-- htap.Votes
CREATE TABLE htap.Votes (
    Id           INT      NOT NULL,
    PostId       INT      NOT NULL,
    VoteTypeId   TINYINT  NOT NULL,
    CreationDate DATE     NOT NULL,
    UserId       INT      NULL,
    BountyAmount INT      NULL,
    CONSTRAINT PK_htap_Votes PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 16777216),
    INDEX IX_htap_Votes_PostId NONCLUSTERED (PostId, CreationDate)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
GO

-- htap.Badges
CREATE TABLE htap.Badges (
    Id     INT           NOT NULL,
    UserId INT           NOT NULL,
    Name   NVARCHAR(50)  NOT NULL,
    Date   DATETIME2(0)  NOT NULL,
    CONSTRAINT PK_htap_Badges PRIMARY KEY NONCLUSTERED HASH (Id)
        WITH (BUCKET_COUNT = 2097152),
    INDEX IX_htap_Badges_UserId NONCLUSTERED (UserId, Date DESC)
) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
GO

PRINT 'htap shema: memory-optimized tablice (dual-store HTAP) uspješno kreirane.';
PRINT 'OLAP sloj: cs.* tablice s columnstore indeksima.';
GO
