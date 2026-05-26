-- =============================================================================
-- HTAPBenchmark: 01_Schema_Baseline.sql
-- Konfiguracija 1: BASELINE
-- Disk-zasnovane tablice s klasičnim Clustered B-tree indeksom
-- Referentna konfiguracija bez optimizacija
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================
-- baseline.Users
-- ============================================================
CREATE TABLE baseline.Users (
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
    CONSTRAINT PK_baseline_Users PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_baseline_Users_Reputation
    ON baseline.Users (Reputation DESC) INCLUDE (DisplayName, Id);
CREATE NONCLUSTERED INDEX IX_baseline_Users_CreationDate
    ON baseline.Users (CreationDate);
GO

-- ============================================================
-- baseline.Posts
-- ============================================================
CREATE TABLE baseline.Posts (
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
    CONSTRAINT PK_baseline_Posts PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_baseline_Posts_OwnerUserId
    ON baseline.Posts (OwnerUserId, CreationDate DESC)
    INCLUDE (Score, PostTypeId, Title, AnswerCount);
CREATE NONCLUSTERED INDEX IX_baseline_Posts_CreationDate
    ON baseline.Posts (CreationDate DESC)
    INCLUDE (PostTypeId, Score, OwnerUserId);
CREATE NONCLUSTERED INDEX IX_baseline_Posts_PostType_Date
    ON baseline.Posts (PostTypeId, CreationDate DESC)
    INCLUDE (Score, OwnerUserId, AnswerCount, AcceptedAnswerId, ViewCount);
GO

-- ============================================================
-- baseline.Comments
-- ============================================================
CREATE TABLE baseline.Comments (
    Id           INT            NOT NULL,
    PostId       INT            NOT NULL,
    Score        INT            NOT NULL DEFAULT 0,
    Text         NVARCHAR(700)  NOT NULL,
    CreationDate DATETIME2(0)   NOT NULL,
    UserId       INT            NULL,
    CONSTRAINT PK_baseline_Comments PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_baseline_Comments_PostId
    ON baseline.Comments (PostId, CreationDate)
    INCLUDE (Score, UserId);
CREATE NONCLUSTERED INDEX IX_baseline_Comments_UserId
    ON baseline.Comments (UserId, CreationDate DESC)
    INCLUDE (PostId, Score);
GO

-- ============================================================
-- baseline.Votes
-- ============================================================
CREATE TABLE baseline.Votes (
    Id           INT      NOT NULL,
    PostId       INT      NOT NULL,
    VoteTypeId   TINYINT  NOT NULL,
    CreationDate DATE     NOT NULL,
    UserId       INT      NULL,
    BountyAmount INT      NULL,
    CONSTRAINT PK_baseline_Votes PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_baseline_Votes_PostId
    ON baseline.Votes (PostId, VoteTypeId)
    INCLUDE (CreationDate);
CREATE NONCLUSTERED INDEX IX_baseline_Votes_CreationDate
    ON baseline.Votes (CreationDate DESC, VoteTypeId)
    INCLUDE (PostId);
GO

-- ============================================================
-- baseline.Badges
-- ============================================================
CREATE TABLE baseline.Badges (
    Id     INT           NOT NULL,
    UserId INT           NOT NULL,
    Name   NVARCHAR(50)  NOT NULL,
    Date   DATETIME2(0)  NOT NULL,
    CONSTRAINT PK_baseline_Badges PRIMARY KEY CLUSTERED (Id)
);
CREATE NONCLUSTERED INDEX IX_baseline_Badges_UserId
    ON baseline.Badges (UserId, Date DESC)
    INCLUDE (Name);
GO

PRINT 'baseline shema: sve tablice i indeksi uspješno kreirani.';
GO
