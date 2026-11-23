CREATE TABLE boats (
    id          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name        NVARCHAR(100)     NOT NULL,
    boat_type   NVARCHAR(50)      NULL,
    length_ft   DECIMAL(6,2)      NOT NULL CHECK (length_ft > 0),
    max_wind_kn DECIMAL(5,1)      NOT NULL CHECK (max_wind_kn > 0),
    max_gust_kn DECIMAL(5,1)      NOT NULL CHECK (max_gust_kn > 0),
    max_wave_m  DECIMAL(4,1)      NOT NULL CHECK (max_wave_m > 0),
    created_at  DATETIME2         NOT NULL DEFAULT SYSUTCDATETIME()
);