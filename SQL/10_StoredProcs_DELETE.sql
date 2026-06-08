-- =============================================================================
-- HTAPBenchmark: 10_StoredProcs_DELETE.sql
-- DELETE stored procedure za sve 4 konfiguracije
--
-- Operacije:
--   usp_DeleteVote        - Simple DELETE: briše jedan glas po ID-u
--   usp_DeletePostVotes   - Complex DELETE: briše sve glasove određenog tipa za post
--
-- Namjena: dopunjava benchmark CRUD coverage-om DELETE operacija
-- IM i HTAP koriste NATIVELY COMPILED procedure (ATOMIC blok, SNAPSHOT isolation)
-- =============================================================================

USE HTAPBenchmark;
GO

-- ===========================================================================
-- BASELINE
-- ===========================================================================

CREATE OR ALTER PROCEDURE baseline.usp_DeleteVote
    @Id INT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM baseline.Votes WHERE Id = @Id;
END;
GO

-- Complex DELETE: briše sve glasove VoteTypeId=2 za dati post
-- (realni scenario: povlačenje svih "spam" oznaka s posta)
CREATE OR ALTER PROCEDURE baseline.usp_DeletePostVotes
    @PostId     INT,
    @VoteTypeId TINYINT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM baseline.Votes
    WHERE PostId = @PostId AND VoteTypeId = @VoteTypeId;
END;
GO

-- ===========================================================================
-- CS (Columnstore)
-- ===========================================================================

CREATE OR ALTER PROCEDURE cs.usp_DeleteVote
    @Id INT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM cs.Votes WHERE Id = @Id;
END;
GO

CREATE OR ALTER PROCEDURE cs.usp_DeletePostVotes
    @PostId     INT,
    @VoteTypeId TINYINT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM cs.Votes
    WHERE PostId = @PostId AND VoteTypeId = @VoteTypeId;
END;
GO

-- ===========================================================================
-- IM (Natively Compiled)
-- NOTE: Natively compiled SPs ne podržavaju CREATE OR ALTER — koristimo DROP+CREATE
-- ===========================================================================

IF OBJECT_ID('im.usp_DeleteVote', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_DeleteVote;
GO
CREATE PROCEDURE im.usp_DeleteVote
    @Id INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DELETE FROM im.Votes WHERE Id = @Id;
END;
GO

IF OBJECT_ID('im.usp_DeletePostVotes', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_DeletePostVotes;
GO
CREATE PROCEDURE im.usp_DeletePostVotes
    @PostId     INT,
    @VoteTypeId TINYINT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DELETE FROM im.Votes
    WHERE PostId = @PostId AND VoteTypeId = @VoteTypeId;
END;
GO

-- ===========================================================================
-- HTAP (Natively Compiled — briše iz htap.Votes)
-- ===========================================================================

IF OBJECT_ID('htap.usp_DeleteVote', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_DeleteVote;
GO
CREATE PROCEDURE htap.usp_DeleteVote
    @Id INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DELETE FROM htap.Votes WHERE Id = @Id;
END;
GO

IF OBJECT_ID('htap.usp_DeletePostVotes', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_DeletePostVotes;
GO
CREATE PROCEDURE htap.usp_DeletePostVotes
    @PostId     INT,
    @VoteTypeId TINYINT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DELETE FROM htap.Votes
    WHERE PostId = @PostId AND VoteTypeId = @VoteTypeId;
END;
GO
