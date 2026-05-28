-- =============================================================================
-- HTAPBenchmark: 08_ResultsSchema.sql
-- Pohrana rezultata benchmarka
-- Tabele: BenchmarkRun, OperationMeasurement, RunSummary
-- =============================================================================

USE HTAPBenchmark;
GO

-- ============================================================
-- results.BenchmarkRun: Metapodaci o jednom mjernom nizu
-- ============================================================
CREATE TABLE results.BenchmarkRun (
    RunId             INT            NOT NULL IDENTITY(1,1),
    RunTimestamp      DATETIME2(3)   NOT NULL DEFAULT SYSUTCDATETIME(),
    Configuration     NVARCHAR(10)   NOT NULL,  -- baseline | cs | im | htap
    OltpOlapRatio     NVARCHAR(10)   NOT NULL,  -- 80_20 | 50_50 | 20_80
    ConcurrencyLevel  INT            NOT NULL,  -- 4 | 16 | 32
    RunNumber         INT            NOT NULL,  -- 1-30
    DurationSeconds   INT            NOT NULL DEFAULT 60,
    WarmupSeconds     INT            NOT NULL DEFAULT 10,
    MachineName       NVARCHAR(100)  NULL,
    SqlServerVersion  NVARCHAR(100)  NULL,
    Notes             NVARCHAR(500)  NULL,
    CONSTRAINT PK_BenchmarkRun PRIMARY KEY CLUSTERED (RunId)
);

CREATE NONCLUSTERED INDEX IX_BenchmarkRun_Config
    ON results.BenchmarkRun (Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber);
GO

-- ============================================================
-- results.OperationMeasurement: Svako pojedinačno mjerenje latencije
-- Ova tablica raste brzo (~100K+ redova po runu)
-- ============================================================
CREATE TABLE results.OperationMeasurement (
    MeasurementId   BIGINT         NOT NULL IDENTITY(1,1),
    RunId           INT            NOT NULL,
    OperationType   NVARCHAR(5)    NOT NULL,  -- OLTP | OLAP
    OperationName   NVARCHAR(50)   NOT NULL,  -- npr. usp_InsertVote
    StartTimestamp  DATETIME2(7)   NOT NULL,
    LatencyMs       FLOAT          NOT NULL,
    Success         BIT            NOT NULL DEFAULT 1,
    ErrorMessage    NVARCHAR(500)  NULL,
    CONSTRAINT PK_OperationMeasurement PRIMARY KEY CLUSTERED (MeasurementId),
    CONSTRAINT FK_Measurement_Run FOREIGN KEY (RunId)
        REFERENCES results.BenchmarkRun (RunId)
);

CREATE NONCLUSTERED INDEX IX_Measurement_RunType
    ON results.OperationMeasurement (RunId, OperationType, LatencyMs);
GO

-- ============================================================
-- results.RunSummary: Agregirana statistika po runu
-- Generiše aplikacija, ili se može izračunati upitom ispod
-- ============================================================
CREATE TABLE results.RunSummary (
    RunId              INT    NOT NULL,
    OltpThroughput     FLOAT  NOT NULL,   -- operacija/sekundi
    OlapThroughput     FLOAT  NOT NULL,   -- upita/sekundi
    OltpLatencyP50     FLOAT  NOT NULL,   -- ms
    OltpLatencyP95     FLOAT  NOT NULL,
    OltpLatencyP99     FLOAT  NOT NULL,
    OlapLatencyP50     FLOAT  NOT NULL,
    OlapLatencyP95     FLOAT  NOT NULL,
    OlapLatencyP99     FLOAT  NOT NULL,
    OltpSuccessRate    FLOAT  NOT NULL,   -- 0.0 - 1.0
    OlapSuccessRate    FLOAT  NOT NULL,
    OltpTotalOps       INT    NOT NULL,
    OlapTotalOps       INT    NOT NULL,
    CONSTRAINT PK_RunSummary PRIMARY KEY CLUSTERED (RunId),
    CONSTRAINT FK_Summary_Run FOREIGN KEY (RunId)
        REFERENCES results.BenchmarkRun (RunId)
);
GO

-- ============================================================
-- Pomoćni upit: izračun percentila iz sirovih mjerenja
-- ============================================================
CREATE OR ALTER VIEW results.vw_RunStatistics AS
WITH Percentiles AS (
    SELECT
        m.RunId,
        m.OperationType,
        COUNT(*)                AS TotalOps,
        SUM(CAST(m.Success AS INT)) AS SuccessOps,
        AVG(m.LatencyMs)        AS AvgLatencyMs,
        MIN(m.LatencyMs)        AS MinLatencyMs,
        MAX(m.LatencyMs)        AS MaxLatencyMs,
        STDEV(m.LatencyMs)      AS StdDevLatencyMs,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY m.LatencyMs)
            OVER (PARTITION BY m.RunId, m.OperationType) AS P50,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY m.LatencyMs)
            OVER (PARTITION BY m.RunId, m.OperationType) AS P95,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY m.LatencyMs)
            OVER (PARTITION BY m.RunId, m.OperationType) AS P99
    FROM results.OperationMeasurement m
    WHERE m.Success = 1
),
Agg AS (
    SELECT DISTINCT RunId, OperationType, TotalOps, SuccessOps,
           AvgLatencyMs, MinLatencyMs, MaxLatencyMs, StdDevLatencyMs,
           P50, P95, P99
    FROM Percentiles
)
SELECT
    r.RunId,
    r.Configuration,
    r.OltpOlapRatio,
    r.ConcurrencyLevel,
    r.RunNumber,
    a.OperationType,
    a.TotalOps,
    a.SuccessOps,
    CAST(a.SuccessOps AS FLOAT) / NULLIF(a.TotalOps, 0) AS SuccessRate,
    CAST(a.SuccessOps AS FLOAT) / NULLIF(r.DurationSeconds, 0) AS Throughput,
    a.AvgLatencyMs,
    a.MinLatencyMs,
    a.MaxLatencyMs,
    a.StdDevLatencyMs,
    a.P50,
    a.P95,
    a.P99
FROM Agg a
INNER JOIN results.BenchmarkRun r ON a.RunId = r.RunId;
GO

-- ============================================================
-- Upit za export CSV podataka za Python analizu
-- ============================================================
/*
SELECT
    r.Configuration,
    r.OltpOlapRatio,
    r.ConcurrencyLevel,
    r.RunNumber,
    m.OperationType,
    m.OperationName,
    m.LatencyMs,
    m.Success
FROM results.OperationMeasurement m
INNER JOIN results.BenchmarkRun r ON m.RunId = r.RunId
WHERE m.Success = 1
ORDER BY r.Configuration, r.OltpOlapRatio, r.ConcurrencyLevel, r.RunNumber;
*/

PRINT 'results shema: sve tablice uspješno kreirane.';
GO
