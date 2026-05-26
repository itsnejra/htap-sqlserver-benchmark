-- =============================================================================
-- HTAPBenchmark: 00_DatabaseSetup.sql
-- Evaluacija performansi HTAP-a u Microsoft SQL Serveru
-- Autor: magistarski rad
-- Opis: Kreiranje baze, filegroup-a i shema
-- NAPOMENA: Prilagodite putanje u @DataPath i @ImPath prema vašem sistemu
-- =============================================================================

USE master;
GO

-- Brisanje i rekreacija baze (OPREZ u produkciji!)
IF EXISTS (SELECT name FROM sys.databases WHERE name = N'HTAPBenchmark')
BEGIN
    ALTER DATABASE HTAPBenchmark SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE HTAPBenchmark;
    PRINT 'Postojeća baza HTAPBenchmark obrisana.';
END
GO

-- ============================================================
-- Kreiranje direktorija (izvršiti jednom, komentirati nakon toga)
-- ============================================================
-- EXEC xp_cmdshell 'mkdir C:\SQLData\HTAPBenchmark';
-- EXEC xp_cmdshell 'mkdir C:\SQLData\HTAPBenchmark\InMemory';

CREATE DATABASE HTAPBenchmark
ON PRIMARY (
    NAME        = N'HTAPBenchmark_Primary',
    FILENAME    = N'C:\SQLData\HTAPBenchmark\HTAPBenchmark.mdf',
    SIZE        = 10240MB,
    MAXSIZE     = UNLIMITED,
    FILEGROWTH  = 2048MB
),
FILEGROUP HTAPBenchmark_MOD CONTAINS MEMORY_OPTIMIZED_DATA (
    NAME        = N'HTAPBenchmark_MOD',
    FILENAME    = N'C:\SQLData\HTAPBenchmark\InMemory'
)
LOG ON (
    NAME        = N'HTAPBenchmark_Log',
    FILENAME    = N'C:\SQLData\HTAPBenchmark\HTAPBenchmark_log.ldf',
    SIZE        = 4096MB,
    MAXSIZE     = UNLIMITED,
    FILEGROWTH  = 1024MB
);
GO

USE HTAPBenchmark;
GO

-- ============================================================
-- Database opcije
-- READ_COMMITTED_SNAPSHOT: eliminira reader-writer blokade za disk-based tablice
-- MEMORY_OPTIMIZED_ELEVATE_TO_SNAPSHOT: automatski podiže iso. nivo za MO tablice
-- ============================================================
ALTER DATABASE HTAPBenchmark SET RECOVERY SIMPLE;
ALTER DATABASE HTAPBenchmark SET PAGE_VERIFY CHECKSUM;
ALTER DATABASE HTAPBenchmark SET READ_COMMITTED_SNAPSHOT ON WITH NO_WAIT;
ALTER DATABASE HTAPBenchmark SET MEMORY_OPTIMIZED_ELEVATE_TO_SNAPSHOT ON;
ALTER DATABASE HTAPBenchmark SET DELAYED_DURABILITY = DISABLED;
GO

-- ============================================================
-- Sheme za svaku konfiguraciju
-- ============================================================
CREATE SCHEMA baseline;  -- Konfiguracija 1: disk B-tree
GO
CREATE SCHEMA cs;        -- Konfiguracija 2: disk + columnstore
GO
CREATE SCHEMA im;        -- Konfiguracija 3: In-Memory OLTP (Hekaton)
GO
CREATE SCHEMA htap;      -- Konfiguracija 4: In-Memory + columnstore (HTAP)
GO
CREATE SCHEMA results;   -- Pohrana rezultata benchmarka
GO

PRINT '======================================================';
PRINT 'Baza HTAPBenchmark uspješno kreirana.';
PRINT 'Sheme: baseline, cs, im, htap, results';
PRINT 'Sljedeći korak: pokrenite 01-04 skripte za kreiranje shema.';
PRINT '======================================================';
GO
