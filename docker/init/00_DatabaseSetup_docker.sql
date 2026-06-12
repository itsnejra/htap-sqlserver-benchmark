-- =============================================================================
-- HTAPBenchmark: 00_DatabaseSetup_docker.sql
-- Linux/Docker verzija (putanje: /var/opt/mssql/data/)
-- =============================================================================

USE master;
GO

IF EXISTS (SELECT name FROM sys.databases WHERE name = N'HTAPBenchmark')
BEGIN
    ALTER DATABASE HTAPBenchmark SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE HTAPBenchmark;
    PRINT 'Postojeća baza HTAPBenchmark obrisana.';
END
GO

CREATE DATABASE HTAPBenchmark
ON PRIMARY (
    NAME        = N'HTAPBenchmark_Primary',
    FILENAME    = N'/var/opt/mssql/data/HTAPBenchmark.mdf',
    SIZE        = 1024MB,
    MAXSIZE     = UNLIMITED,
    FILEGROWTH  = 1024MB
),
FILEGROUP HTAPBenchmark_MOD CONTAINS MEMORY_OPTIMIZED_DATA (
    NAME        = N'HTAPBenchmark_MOD',
    FILENAME    = N'/var/opt/mssql/data/HTAPBenchmark_InMemory'
)
LOG ON (
    NAME        = N'HTAPBenchmark_Log',
    FILENAME    = N'/var/opt/mssql/data/HTAPBenchmark_log.ldf',
    SIZE        = 512MB,
    MAXSIZE     = UNLIMITED,
    FILEGROWTH  = 512MB
);
GO

USE HTAPBenchmark;
GO

ALTER DATABASE HTAPBenchmark SET RECOVERY SIMPLE;
ALTER DATABASE HTAPBenchmark SET PAGE_VERIFY CHECKSUM;
ALTER DATABASE HTAPBenchmark SET READ_COMMITTED_SNAPSHOT ON WITH NO_WAIT;
ALTER DATABASE HTAPBenchmark SET MEMORY_OPTIMIZED_ELEVATE_TO_SNAPSHOT ON;
ALTER DATABASE HTAPBenchmark SET DELAYED_DURABILITY = DISABLED;
GO

CREATE SCHEMA baseline;
GO
CREATE SCHEMA cs;
GO
CREATE SCHEMA im;
GO
CREATE SCHEMA htap;
GO
CREATE SCHEMA results;
GO

PRINT '======================================================';
PRINT 'Baza HTAPBenchmark uspješno kreirana (Docker/Linux).';
PRINT 'Sheme: baseline, cs, im, htap, results';
PRINT '======================================================';
GO
