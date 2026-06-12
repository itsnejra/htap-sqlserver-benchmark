-- =============================================================================
-- HTAPBenchmark: 01_attach_stackoverflow.sql
-- Attach StackOverflow2010.mdf koji je kopiran u /var/opt/mssql/data/
-- FOR ATTACH_REBUILD_LOG radi i bez LDF fajla
-- =============================================================================

USE master;
GO

IF DB_ID('StackOverflow2010') IS NOT NULL
BEGIN
    PRINT 'StackOverflow2010 već postoji — preskačemo attach.';
END
ELSE
BEGIN
    PRINT 'Attachujem /var/opt/mssql/data/StackOverflow2010.mdf...';

    CREATE DATABASE StackOverflow2010
    ON (FILENAME = N'/var/opt/mssql/data/StackOverflow2010.mdf')
    FOR ATTACH_REBUILD_LOG;

    PRINT '=== StackOverflow2010 attach završen. ===';
END
GO
