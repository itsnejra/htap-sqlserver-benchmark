-- =============================================================================
-- HTAPBenchmark: 11_StoredProcs_ComplexUPDATE.sql
-- Complex UPDATE stored procedure za sve 4 konfiguracije
--
-- usp_UpdateUserReputation(@UserId INT)
--   Complex UPDATE jer:
--     1. Čita iz tabele Posts (COUNT odgovora korisnika)
--     2. Piše u tabelu Users (ažurira Reputation)
--   Simulira realnu poslovnu logiku: reputacija korisnika = f(broj odgovora)
--
-- Baseline/CS: CREATE OR ALTER (regular T-SQL)
-- IM/HTAP:     DROP + CREATE WITH NATIVE_COMPILATION, SCHEMABINDING
-- =============================================================================

USE HTAPBenchmark;
GO

-- ===========================================================================
-- BASELINE
-- ===========================================================================
CREATE OR ALTER PROCEDURE baseline.usp_UpdateUserReputation
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE baseline.Users
    SET Reputation = Reputation + (
        SELECT COUNT(*)
        FROM   baseline.Posts
        WHERE  OwnerUserId = @UserId
          AND  PostTypeId  = 2          -- samo odgovori (PostTypeId=2)
    )
    WHERE Id = @UserId;
END;
GO

-- ===========================================================================
-- CS (Columnstore)
-- ===========================================================================
CREATE OR ALTER PROCEDURE cs.usp_UpdateUserReputation
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE cs.Users
    SET Reputation = Reputation + (
        SELECT COUNT(*)
        FROM   cs.Posts
        WHERE  OwnerUserId = @UserId
          AND  PostTypeId  = 2
    )
    WHERE Id = @UserId;
END;
GO

-- ===========================================================================
-- IM (Natively Compiled)
-- Nativno kompajlirane procedure ne podrzavaju korelisane subupite u UPDATE,
-- koristimo DECLARE varijablu kao medjukorak.
-- ===========================================================================
IF OBJECT_ID('im.usp_UpdateUserReputation', 'P') IS NOT NULL
    DROP PROCEDURE im.usp_UpdateUserReputation;
GO
CREATE PROCEDURE im.usp_UpdateUserReputation
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DECLARE @AnswerCount INT;
    SELECT @AnswerCount = COUNT(*)
    FROM   im.Posts
    WHERE  OwnerUserId = @UserId
      AND  PostTypeId  = 2;
    UPDATE im.Users
    SET    Reputation  = Reputation + @AnswerCount
    WHERE  Id          = @UserId;
END;
GO

-- ===========================================================================
-- HTAP (Natively Compiled — piše u htap.Users, čita iz htap.Posts)
-- ===========================================================================
IF OBJECT_ID('htap.usp_UpdateUserReputation', 'P') IS NOT NULL
    DROP PROCEDURE htap.usp_UpdateUserReputation;
GO
CREATE PROCEDURE htap.usp_UpdateUserReputation
    @UserId INT
WITH NATIVE_COMPILATION, SCHEMABINDING
AS BEGIN ATOMIC WITH (TRANSACTION ISOLATION LEVEL = SNAPSHOT, LANGUAGE = N'English')
    DECLARE @AnswerCount INT;
    SELECT @AnswerCount = COUNT(*)
    FROM   htap.Posts
    WHERE  OwnerUserId = @UserId
      AND  PostTypeId  = 2;
    UPDATE htap.Users
    SET    Reputation  = Reputation + @AnswerCount
    WHERE  Id          = @UserId;
END;
GO

PRINT 'Complex UPDATE stored procedure (usp_UpdateUserReputation) za sve 4 konfiguracije uspjesno kreirana.';
GO
