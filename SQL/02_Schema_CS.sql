-- =============================================================================
-- HTAPBenchmark: 02_Schema_CS.sql
-- Konfiguracija 2: CS (Columnstore)
-- Disk-zasnovane tablice + Nonclustered Columnstore indeks
-- NAPOMENA: Nonclustered columnstore ne uključuje LOB kolone (NVARCHAR(MAX))
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================
-- cs.Users
-- ============================================================
CREATE TABLE cs.Users (
    Id               INT            NOT NULL,
    Reputation       INT            NOT NULL DEFAULT 1,
    CreationDate     DATETIME2(0)   NOT NULL,
    DisplayName      NVARCHAR(40)   NOT NULL,
    LastAccessDate   DATETIME2(0)   NOT NULL,
    WebsiteUrl       NVARCHAR(200)  NULL,
    Location         NVARCHAR(100)  NULL,
    AboutMe          NVARCHAR(MAX)  NULL,
    Views            INT            NOT NULL DEFAULT 0,
    UpVotes          INT            NOT NULL DEFAULT 0,
    DownVotes        INT            NOT NULL DEFAULT 0,
    Age              INT            NULL,
    AccountId        INT            NULL,
    CONSTRAINT PK_cs_Users PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_cs_Users_Reputation
    ON cs.Users (Reputation DESC) INCLUDE (DisplayName, Id);
-- Columnstore za analitičke upite (bez MAX kolona)
CREATE NONCLUSTERED COLUMNSTORE INDEX NCSI_cs_Users
    ON cs.Users (Id, Reputation, CreationDate, LastAccessDate, Views, UpVotes, DownVotes, Age, AccountId);
GO

-- ============================================================
-- cs.Posts
-- ============================================================
CREATE TABLE cs.Posts (
    Id                    INT            NOT NULL,
    PostTypeId            TINYINT        NOT NULL,
    ParentId              INT            NULL,
    AcceptedAnswerId      INT            NULL,
    CreationDate          DATETIME2(0)   NOT NULL,
    Score                 INT            NOT NULL DEFAULT 0,
    ViewCount             INT            NOT NULL DEFAULT 0,
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
    AnswerCount           INT            NOT NULL DEFAULT 0,
    CommentCount          INT            NOT NULL DEFAULT 0,
    FavoriteCount         INT            NOT NULL DEFAULT 0,
    CONSTRAINT PK_cs_Posts PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_cs_Posts_OwnerUserId
    ON cs.Posts (OwnerUserId, CreationDate DESC)
    INCLUDE (Score, PostTypeId, Title, AnswerCount);
-- Columnstore: sve kolone osim LOB (Body) i VARCHAR (Title, Tags, LastEditorDisplayName)
CREATE NONCLUSTERED COLUMNSTORE INDEX NCSI_cs_Posts
    ON cs.Posts (
        Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate,
        Score, ViewCount, OwnerUserId, LastEditorUserId,
        LastEditDate, LastActivityDate, CommunityOwnedDate, ClosedDate,
        AnswerCount, CommentCount, FavoriteCount
    );
GO

-- ============================================================
-- cs.Comments
-- ============================================================
CREATE TABLE cs.Comments (
    Id           INT            NOT NULL,
    PostId       INT            NOT NULL,
    Score        INT            NOT NULL DEFAULT 0,
    Text         NVARCHAR(700)  NOT NULL,
    CreationDate DATETIME2(0)   NOT NULL,
    UserId       INT            NULL,
    CONSTRAINT PK_cs_Comments PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_cs_Comments_PostId
    ON cs.Comments (PostId, CreationDate) INCLUDE (Score, UserId);
CREATE NONCLUSTERED COLUMNSTORE INDEX NCSI_cs_Comments
    ON cs.Comments (Id, PostId, Score, CreationDate, UserId);
GO

-- ============================================================
-- cs.Votes
-- ============================================================
CREATE TABLE cs.Votes (
    Id           INT      NOT NULL,
    PostId       INT      NOT NULL,
    VoteTypeId   TINYINT  NOT NULL,
    CreationDate DATE     NOT NULL,
    UserId       INT      NULL,
    BountyAmount INT      NULL,
    CONSTRAINT PK_cs_Votes PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_cs_Votes_PostId
    ON cs.Votes (PostId, VoteTypeId) INCLUDE (CreationDate);
CREATE NONCLUSTERED COLUMNSTORE INDEX NCSI_cs_Votes
    ON cs.Votes (Id, PostId, VoteTypeId, CreationDate, UserId, BountyAmount);
GO

-- ============================================================
-- cs.Badges
-- ============================================================
CREATE TABLE cs.Badges (
    Id     INT           NOT NULL,
    UserId INT           NOT NULL,
    Name   NVARCHAR(50)  NOT NULL,
    Date   DATETIME2(0)  NOT NULL,
    CONSTRAINT PK_cs_Badges PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_cs_Badges_UserId
    ON cs.Badges (UserId, Date DESC) INCLUDE (Name);
CREATE NONCLUSTERED COLUMNSTORE INDEX NCSI_cs_Badges
    ON cs.Badges (Id, UserId, Date);
GO

-- ============================================================
-- Kompresija columnstore row groups nakon učitavanja podataka
-- Pokrenuti NAKON 05_LoadData.sql
-- ============================================================
-- ALTER INDEX NCSI_cs_Posts     ON cs.Posts     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
-- ALTER INDEX NCSI_cs_Votes     ON cs.Votes     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
-- ALTER INDEX NCSI_cs_Comments  ON cs.Comments  REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
-- ALTER INDEX NCSI_cs_Users     ON cs.Users     REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
-- ALTER INDEX NCSI_cs_Badges    ON cs.Badges    REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);

PRINT 'cs shema: tablice s columnstore indeksima uspješno kreirane.';
GO
