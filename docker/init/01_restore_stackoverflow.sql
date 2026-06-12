-- =============================================================================
-- HTAPBenchmark: 01_restore_stackoverflow.sql
-- Dinamički restore StackOverflow2010.bak na Linux/Docker SQL Server
-- Koristi RESTORE FILELISTONLY da dobije logička imena fajlova iz .bak-a
-- =============================================================================

USE master;
GO

IF DB_ID('StackOverflow2010') IS NOT NULL
BEGIN
    PRINT 'StackOverflow2010 već postoji — preskačemo restore.';
END
ELSE
BEGIN
    PRINT 'Čitam listu fajlova iz /backups/StackOverflow2010.bak...';

    CREATE TABLE #fileList (
        LogicalName         NVARCHAR(128)    NULL,
        PhysicalName        NVARCHAR(260)    NULL,
        [Type]              CHAR(1)          NULL,
        FileGroupName       NVARCHAR(128)    NULL,
        Size                NUMERIC(20,0)    NULL,
        MaxSize             NUMERIC(20,0)    NULL,
        FileId              BIGINT           NULL,
        CreateLSN           NUMERIC(25,0)    NULL,
        DropLSN             NUMERIC(25,0)    NULL,
        UniqueId            UNIQUEIDENTIFIER NULL,
        ReadOnlyLSN         NUMERIC(25,0)    NULL,
        ReadWriteLSN        NUMERIC(25,0)    NULL,
        BackupSizeInBytes   BIGINT           NULL,
        SourceBlockSize     INT              NULL,
        FileGroupId         INT              NULL,
        LogGroupGUID        UNIQUEIDENTIFIER NULL,
        DifferentialBaseLSN NUMERIC(25,0)    NULL,
        DifferentialBaseGUID UNIQUEIDENTIFIER NULL,
        IsReadOnly          BIT              NULL,
        IsPresent           BIT              NULL,
        TDEThumbprint       VARBINARY(32)    NULL,
        SnapshotUrl         NVARCHAR(360)    NULL
    );

    INSERT INTO #fileList
    EXEC ('RESTORE FILELISTONLY FROM DISK = ''/backups/StackOverflow2010.bak''');

    DECLARE @sql    NVARCHAR(MAX) = '';
    DECLARE @moves  NVARCHAR(MAX) = '';
    DECLARE @ext    NVARCHAR(4);
    DECLARE @rownum INT;

    -- Data fajlovi: prvi dobija .mdf, ostali .ndf
    DECLARE data_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT LogicalName,
               ROW_NUMBER() OVER (ORDER BY FileId) AS rn
        FROM #fileList
        WHERE [Type] = 'D';

    DECLARE @logName NVARCHAR(128);
    OPEN data_cur;
    FETCH NEXT FROM data_cur INTO @logName, @rownum;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @ext = CASE WHEN @rownum = 1 THEN '.mdf' ELSE '.ndf' END;
        SET @moves = @moves + ', MOVE ''' + @logName + ''' TO ''/var/opt/mssql/data/' + @logName + @ext + '''';
        FETCH NEXT FROM data_cur INTO @logName, @rownum;
    END
    CLOSE data_cur;
    DEALLOCATE data_cur;

    -- Log fajlovi
    DECLARE log_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT LogicalName FROM #fileList WHERE [Type] = 'L';

    OPEN log_cur;
    FETCH NEXT FROM log_cur INTO @logName;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @moves = @moves + ', MOVE ''' + @logName + ''' TO ''/var/opt/mssql/data/' + @logName + '.ldf''';
        FETCH NEXT FROM log_cur INTO @logName;
    END
    CLOSE log_cur;
    DEALLOCATE log_cur;

    DROP TABLE #fileList;

    SET @sql = 'RESTORE DATABASE StackOverflow2010 '
             + 'FROM DISK = ''/backups/StackOverflow2010.bak'' '
             + 'WITH REPLACE, RECOVERY, STATS = 10'
             + @moves + ';';

    PRINT 'Pokrećem restore...';
    EXEC sp_executesql @sql;

    PRINT '=== StackOverflow2010 restore završen. ===';
END
GO
