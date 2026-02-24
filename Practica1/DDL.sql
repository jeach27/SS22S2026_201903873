-- ============================================================
--  PRÁCTICA 1 - Seminario de Sistemas 2
--  DDL
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'VuelosBI')
    CREATE DATABASE VuelosBI;
GO

USE VuelosBI;
GO

-- ------------------------------------------------------------
-- DROP de tablas en orden
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.Hechos_Vuelo',       'U') IS NOT NULL DROP TABLE dbo.Hechos_Vuelo;
IF OBJECT_ID('dbo.DIM_AEROLINEA',      'U') IS NOT NULL DROP TABLE dbo.DIM_AEROLINEA;
IF OBJECT_ID('dbo.DIM_PASAJERO',       'U') IS NOT NULL DROP TABLE dbo.DIM_PASAJERO;
IF OBJECT_ID('dbo.DIM_AEROPUERTO',     'U') IS NOT NULL DROP TABLE dbo.DIM_AEROPUERTO;
IF OBJECT_ID('dbo.DIM_TIEMPO',         'U') IS NOT NULL DROP TABLE dbo.DIM_TIEMPO;
IF OBJECT_ID('dbo.DIM_CANAL',          'U') IS NOT NULL DROP TABLE dbo.DIM_CANAL;
IF OBJECT_ID('dbo.DIM_METODO_PAGO',    'U') IS NOT NULL DROP TABLE dbo.DIM_METODO_PAGO;
IF OBJECT_ID('dbo.DIM_AERONAVE',       'U') IS NOT NULL DROP TABLE dbo.DIM_AERONAVE;
IF OBJECT_ID('dbo.DIM_CLASE',          'U') IS NOT NULL DROP TABLE dbo.DIM_CLASE;
IF OBJECT_ID('dbo.DIM_ESTADO_VUELO',   'U') IS NOT NULL DROP TABLE dbo.DIM_ESTADO_VUELO;
GO

-- ============================================================
-- DIMENSIONES
-- ============================================================

-- ------------------------------------------------------------
-- DIM_AEROLINEA
-- Fuente: Dataset_1 (airline_code, airline_name)
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_AEROLINEA (
    ID_Aerolinea    INT           IDENTITY(1,1) PRIMARY KEY,
    Codigo          VARCHAR(10)   NOT NULL UNIQUE,   -- e.g. 'AV', 'DL'
    Nombre          VARCHAR(100)  NOT NULL            -- e.g. 'Avianca', 'Delta'
);
GO

-- ------------------------------------------------------------
-- DIM_PASAJERO
-- Fuente: Dataset_2 (passenger_id, passenger_gender,
--                    passenger_age, passenger_nationality)
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_PASAJERO (
    ID_Pasajero         INT           IDENTITY(1,1) PRIMARY KEY,
    Passenger_UUID      VARCHAR(50)   NOT NULL UNIQUE, -- UUID original
    Genero              CHAR(1)       NOT NULL          -- 'M', 'F', 'X' (normalizado)
        CHECK (Genero IN ('M','F','X')),
    Edad                TINYINT       NULL,             -- NULL si viene vacío
    Nacionalidad        CHAR(2)       NULL              -- código ISO 2 letras, e.g. 'GT'
);
GO

-- ------------------------------------------------------------
-- DIM_AEROPUERTO
-- Fuente: Dataset_1 (origin_airport / destination_airport)
--         + enriquecimiento manual (Nombre, Pais)
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_AEROPUERTO (
    ID_Aeropuerto   INT           IDENTITY(1,1) PRIMARY KEY,
    Codigo          CHAR(3)       NOT NULL UNIQUE,  -- IATA en mayúsculas
    Nombre          VARCHAR(100)  NOT NULL,
    Pais            VARCHAR(60)   NOT NULL
);
GO

-- ------------------------------------------------------------
-- DIM_TIEMPO
-- Generada por el ETL para todas las fechas relevantes.
-- Una misma tabla sirve como rol-playing dimension
-- (Salida, Llegada y Reserva apuntan a ella).
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_TIEMPO (
    ID_Fecha        INT     PRIMARY KEY,  
    Fecha_Completa  DATE    NOT NULL,
    Año             SMALLINT NOT NULL,
    Mes             TINYINT  NOT NULL,
    Nombre_Mes      VARCHAR(15) NOT NULL,
    Dia             TINYINT  NOT NULL,
    Dia_Semana      TINYINT  NOT NULL,   
    Trimestre       TINYINT  NOT NULL,
    Es_Fin_Semana   BIT      NOT NULL DEFAULT 0
);
GO

-- ------------------------------------------------------------
-- DIM_CANAL
-- Fuente: Dataset_2 (sales_channel)
-- Valores: APP, AEROPUERTO, CALL_CENTER, WEB, AGENCIA
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_CANAL (
    ID_Canal    INT          IDENTITY(1,1) PRIMARY KEY,
    Canal       VARCHAR(30)  NOT NULL UNIQUE
);
GO

-- ------------------------------------------------------------
-- DIM_METODO_PAGO
-- Fuente: Dataset_2 (payment_method)
-- Valores: EFECTIVO, TARJETA, TRANSFERENCIA, PAYPAL, PUNTOS
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_METODO_PAGO (
    ID_Metodo       INT         IDENTITY(1,1) PRIMARY KEY,
    Metodo_Pago     VARCHAR(30) NOT NULL UNIQUE
);
GO

-- ------------------------------------------------------------
-- DIM_AERONAVE
-- Fuente: Dataset_1 (aircraft_type)
-- Valores: B739, A320, CRJ9, B787, B777, etc.
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_AERONAVE (
    ID_Aeronave     INT         IDENTITY(1,1) PRIMARY KEY,
    Tipo_Aeronave   VARCHAR(10) NOT NULL UNIQUE
);
GO

-- ------------------------------------------------------------
-- DIM_CLASE
-- Fuente: Dataset_1 (cabin_class)
-- Valores: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_CLASE (
    ID_Clase        INT         IDENTITY(1,1) PRIMARY KEY,
    Clase_Cabina    VARCHAR(20) NOT NULL UNIQUE
);
GO

-- ------------------------------------------------------------
-- DIM_ESTADO_VUELO
-- Fuente: Dataset_1 (status)
-- Valores: ON_TIME, DELAYED, CANCELLED, DIVERTED
-- ------------------------------------------------------------
CREATE TABLE dbo.DIM_ESTADO_VUELO (
    ID_Estado_Vuelo INT         IDENTITY(1,1) PRIMARY KEY,
    Estado          VARCHAR(15) NOT NULL UNIQUE
);
GO

-- ============================================================
-- TABLA DE HECHOS
-- ============================================================

-- ------------------------------------------------------------
-- Hechos_Vuelo
-- Granularidad: un registro por vuelo-pasajero
-- Medidas: Precio_Ticket, Precio_Original, Total_Maletas,
--          Maletas_Chequeadas, Duracion, Retraso
-- ------------------------------------------------------------
CREATE TABLE dbo.Hechos_Vuelo (
    ID_Fact                 INT           IDENTITY(1,1) PRIMARY KEY,

    -- Claves foráneas a dimensiones
    ID_Aerolinea            INT           NOT NULL,
    ID_Pasajero             INT           NOT NULL,
    ID_Aeropuerto_Origen    INT           NOT NULL,
    ID_Aeropuerto_Destino   INT           NOT NULL,

    -- Rol-playing sobre DIM_TIEMPO
    ID_Fecha_Salida         INT           NULL,   -- NULL si vuelo cancelado sin fecha
    ID_Fecha_Llegada        INT           NULL,
    ID_Fecha_Reserva        INT           NOT NULL,

    ID_Canal                INT           NOT NULL,
    ID_Metodo               INT           NOT NULL,
    ID_Aeronave             INT           NOT NULL,
    ID_Clase                INT           NOT NULL,
    ID_Estado_Vuelo         INT           NOT NULL,

    -- Medidas
    Precio_Ticket           DECIMAL(10,2) NOT NULL,  -- precio en USD (normalizado)
    Moneda_Original         CHAR(3)       NOT NULL,  -- 'USD','GTQ','EUR','MXN'
    Precio_Original         DECIMAL(10,2) NOT NULL,  -- precio en moneda original
    Total_Maletas           TINYINT       NOT NULL DEFAULT 0,
    Maletas_Chequeadas      TINYINT       NOT NULL DEFAULT 0,
    Duracion                SMALLINT      NULL,       -- minutos, NULL si cancelado
    Retraso                 SMALLINT      NULL,       -- minutos, NULL si no aplica
    Cantidad_Vuelo          TINYINT       NOT NULL DEFAULT 1, -- siempre 1

    -- FK constraints
    CONSTRAINT FK_Fact_Aerolinea        FOREIGN KEY (ID_Aerolinea)
        REFERENCES dbo.DIM_AEROLINEA (ID_Aerolinea),

    CONSTRAINT FK_Fact_Pasajero         FOREIGN KEY (ID_Pasajero)
        REFERENCES dbo.DIM_PASAJERO (ID_Pasajero),

    CONSTRAINT FK_Fact_AeropOrigen      FOREIGN KEY (ID_Aeropuerto_Origen)
        REFERENCES dbo.DIM_AEROPUERTO (ID_Aeropuerto),

    CONSTRAINT FK_Fact_AeropDestino     FOREIGN KEY (ID_Aeropuerto_Destino)
        REFERENCES dbo.DIM_AEROPUERTO (ID_Aeropuerto),

    CONSTRAINT FK_Fact_FechaSalida      FOREIGN KEY (ID_Fecha_Salida)
        REFERENCES dbo.DIM_TIEMPO (ID_Fecha),

    CONSTRAINT FK_Fact_FechaLlegada     FOREIGN KEY (ID_Fecha_Llegada)
        REFERENCES dbo.DIM_TIEMPO (ID_Fecha),

    CONSTRAINT FK_Fact_FechaReserva     FOREIGN KEY (ID_Fecha_Reserva)
        REFERENCES dbo.DIM_TIEMPO (ID_Fecha),

    CONSTRAINT FK_Fact_Canal            FOREIGN KEY (ID_Canal)
        REFERENCES dbo.DIM_CANAL (ID_Canal),

    CONSTRAINT FK_Fact_Metodo           FOREIGN KEY (ID_Metodo)
        REFERENCES dbo.DIM_METODO_PAGO (ID_Metodo),

    CONSTRAINT FK_Fact_Aeronave         FOREIGN KEY (ID_Aeronave)
        REFERENCES dbo.DIM_AERONAVE (ID_Aeronave),

    CONSTRAINT FK_Fact_Clase            FOREIGN KEY (ID_Clase)
        REFERENCES dbo.DIM_CLASE (ID_Clase),

    CONSTRAINT FK_Fact_EstadoVuelo      FOREIGN KEY (ID_Estado_Vuelo)
        REFERENCES dbo.DIM_ESTADO_VUELO (ID_Estado_Vuelo)
);
GO

-- ============================================================
-- ÍNDICES para optimizar consultas analíticas
-- ============================================================
CREATE INDEX IX_Fact_Aerolinea      ON dbo.Hechos_Vuelo (ID_Aerolinea);
CREATE INDEX IX_Fact_AeropDestino   ON dbo.Hechos_Vuelo (ID_Aeropuerto_Destino);
CREATE INDEX IX_Fact_FechaSalida    ON dbo.Hechos_Vuelo (ID_Fecha_Salida);
CREATE INDEX IX_Fact_FechaReserva   ON dbo.Hechos_Vuelo (ID_Fecha_Reserva);
CREATE INDEX IX_Fact_EstadoVuelo    ON dbo.Hechos_Vuelo (ID_Estado_Vuelo);
CREATE INDEX IX_Fact_Canal          ON dbo.Hechos_Vuelo (ID_Canal);
GO

-- ============================================================
-- CARGA DE CATÁLOGOS ESTÁTICOS (aeropuertos conocidos)
-- ============================================================
INSERT INTO dbo.DIM_AEROPUERTO (Codigo, Nombre, Pais) VALUES
('GUA', 'Aeropuerto Internacional La Aurora',          'Guatemala'),
('MEX', 'Aeropuerto Internacional Benito Juárez',      'México'),
('MIA', 'Miami International Airport',                 'Estados Unidos'),
('JFK', 'John F. Kennedy International Airport',       'Estados Unidos'),
('LAX', 'Los Angeles International Airport',           'Estados Unidos'),
('BOG', 'Aeropuerto Internacional El Dorado',          'Colombia'),
('LIM', 'Aeropuerto Internacional Jorge Chávez',       'Perú'),
('PTY', 'Aeropuerto Internacional de Tocumen',         'Panamá'),
('SAP', 'Aeropuerto Internacional Ramón Villeda Morales','Honduras'),
('SJO', 'Aeropuerto Internacional Juan Santamaría',    'Costa Rica'),
('SAL', 'Aeropuerto Internacional Monseñor Óscar Romero','El Salvador'),
('HAV', 'Aeropuerto Internacional José Martí',         'Cuba'),
('CUN', 'Aeropuerto Internacional de Cancún',          'México'),
('BCN', 'Aeropuerto de Barcelona-El Prat',             'España'),
('MAD', 'Aeropuerto Adolfo Suárez Madrid-Barajas',    'España');
GO

PRINT 'Modelo multidimensional VuelosBI creado exitosamente.';
GO