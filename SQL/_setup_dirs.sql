EXEC sp_configure 'show advanced options', 1; RECONFIGURE WITH OVERRIDE;
EXEC sp_configure 'xp_cmdshell', 1;         RECONFIGURE WITH OVERRIDE;
GO
EXEC xp_cmdshell 'mkdir C:\SQLData\HTAPBenchmark\InMemory 2>nul', NO_OUTPUT;
GO
EXEC xp_cmdshell 'icacls C:\SQLData /grant "NT SERVICE\MSSQLSERVER:(OI)(CI)F" /T', NO_OUTPUT;
GO
EXEC xp_cmdshell 'dir C:\SQLData\HTAPBenchmark';
GO
EXEC sp_configure 'xp_cmdshell', 0; RECONFIGURE WITH OVERRIDE;
GO
