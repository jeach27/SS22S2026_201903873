-- ============================================================
--  PRÁCTICA 1 - Seminario de Sistemas 2
--  Consultas Analíticas
-- ============================================================

USE VuelosBI;
GO

-- ============================================================
-- VALIDACIÓN DE CARGA
-- Verificar que los datos se cargaron correctamente
-- ============================================================

-- Conteo de registros por tabla
SELECT 'DIM_AEROLINEA'    AS Tabla, COUNT(*) AS Registros FROM dbo.DIM_AEROLINEA    UNION ALL
SELECT 'DIM_PASAJERO',              COUNT(*)              FROM dbo.DIM_PASAJERO      UNION ALL
SELECT 'DIM_AEROPUERTO',            COUNT(*)              FROM dbo.DIM_AEROPUERTO    UNION ALL
SELECT 'DIM_TIEMPO',                COUNT(*)              FROM dbo.DIM_TIEMPO        UNION ALL
SELECT 'DIM_CANAL',                 COUNT(*)              FROM dbo.DIM_CANAL         UNION ALL
SELECT 'DIM_METODO_PAGO',           COUNT(*)              FROM dbo.DIM_METODO_PAGO   UNION ALL
SELECT 'DIM_AERONAVE',              COUNT(*)              FROM dbo.DIM_AERONAVE      UNION ALL
SELECT 'DIM_CLASE',                 COUNT(*)              FROM dbo.DIM_CLASE         UNION ALL
SELECT 'DIM_ESTADO_VUELO',          COUNT(*)              FROM dbo.DIM_ESTADO_VUELO  UNION ALL
SELECT 'Hechos_Vuelo',              COUNT(*)              FROM dbo.Hechos_Vuelo;
GO

-- Verificar integridad: ningún FK debe quedar huérfano
SELECT COUNT(*) AS Huerfanos_Aerolinea
FROM dbo.Hechos_Vuelo h
LEFT JOIN dbo.DIM_AEROLINEA a ON h.ID_Aerolinea = a.ID_Aerolinea
WHERE a.ID_Aerolinea IS NULL;

SELECT COUNT(*) AS Huerfanos_Aeropuerto_Origen
FROM dbo.Hechos_Vuelo h
LEFT JOIN dbo.DIM_AEROPUERTO ap ON h.ID_Aeropuerto_Origen = ap.ID_Aeropuerto
WHERE ap.ID_Aeropuerto IS NULL;
GO

-- Rango de fechas cargadas
SELECT
    MIN(Fecha_Completa) AS Fecha_Mas_Antigua,
    MAX(Fecha_Completa) AS Fecha_Mas_Reciente,
    COUNT(DISTINCT Fecha_Completa) AS Dias_Distintos
FROM dbo.DIM_TIEMPO;
GO

-- ============================================================
-- INDICADORES DE VUELOS
-- ============================================================

-- Total de vuelos y distribución por estado
SELECT
    e.Estado,
    COUNT(*)                                      AS Total_Vuelos,
    CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS DECIMAL(5,2)) AS Porcentaje
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_ESTADO_VUELO e ON h.ID_Estado_Vuelo = e.ID_Estado_Vuelo
GROUP BY e.Estado
ORDER BY Total_Vuelos DESC;
GO

-- Top 5 aeropuertos de destino más frecuentes
SELECT TOP 5
    ap.Codigo,
    ap.Nombre,
    ap.Pais,
    COUNT(*) AS Total_Vuelos_Llegada
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_AEROPUERTO ap ON h.ID_Aeropuerto_Destino = ap.ID_Aeropuerto
GROUP BY ap.Codigo, ap.Nombre, ap.Pais
ORDER BY Total_Vuelos_Llegada DESC;
GO

-- Top 5 rutas más frecuentes (Origen → Destino)
SELECT TOP 5
    origen.Codigo   AS Origen,
    destino.Codigo  AS Destino,
    origen.Pais     AS Pais_Origen,
    destino.Pais    AS Pais_Destino,
    COUNT(*)        AS Total_Vuelos
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_AEROPUERTO origen  ON h.ID_Aeropuerto_Origen  = origen.ID_Aeropuerto
JOIN dbo.DIM_AEROPUERTO destino ON h.ID_Aeropuerto_Destino = destino.ID_Aeropuerto
GROUP BY origen.Codigo, origen.Pais, destino.Codigo, destino.Pais
ORDER BY Total_Vuelos DESC;
GO

-- Vuelos por aerolínea con promedio de retraso
SELECT
    a.Codigo,
    a.Nombre                                AS Aerolinea,
    COUNT(*)                                AS Total_Vuelos,
    SUM(CASE WHEN e.Estado = 'CANCELLED' THEN 1 ELSE 0 END) AS Cancelados,
    SUM(CASE WHEN e.Estado = 'DELAYED'   THEN 1 ELSE 0 END) AS Demorados,
    AVG(CAST(h.Retraso AS FLOAT))           AS Promedio_Retraso_Min
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_AEROLINEA    a ON h.ID_Aerolinea    = a.ID_Aerolinea
JOIN dbo.DIM_ESTADO_VUELO e ON h.ID_Estado_Vuelo = e.ID_Estado_Vuelo
GROUP BY a.Codigo, a.Nombre
ORDER BY Total_Vuelos DESC;
GO

-- Duración promedio de vuelo por tipo de aeronave
SELECT
    av.Tipo_Aeronave,
    COUNT(*)                        AS Total_Vuelos,
    AVG(h.Duracion)                 AS Duracion_Promedio_Min,
    MIN(h.Duracion)                 AS Duracion_Minima,
    MAX(h.Duracion)                 AS Duracion_Maxima
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_AERONAVE av ON h.ID_Aeronave = av.ID_Aeronave
WHERE h.Duracion IS NOT NULL
GROUP BY av.Tipo_Aeronave
ORDER BY Duracion_Promedio_Min DESC;
GO

-- ============================================================
-- INDICADORES DE PASAJEROS
-- ============================================================

-- Distribución de vuelos por género del pasajero
SELECT
    p.Genero,
    COUNT(*)                                      AS Total_Vuelos,
    CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS DECIMAL(5,2)) AS Porcentaje
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_PASAJERO p ON h.ID_Pasajero = p.ID_Pasajero
GROUP BY p.Genero
ORDER BY Total_Vuelos DESC;
GO

-- Top 5 nacionalidades con más vuelos
SELECT TOP 5
    ISNULL(p.Nacionalidad, 'NO_ESPECIFICADO') AS Nacionalidad,
    COUNT(*) AS Total_Vuelos,
    AVG(CAST(p.Edad AS FLOAT)) AS Edad_Promedio
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_PASAJERO p ON h.ID_Pasajero = p.ID_Pasajero
GROUP BY p.Nacionalidad
ORDER BY Total_Vuelos DESC;
GO

-- Distribución por clase de cabina y género
SELECT
    cl.Clase_Cabina,
    p.Genero,
    COUNT(*) AS Total_Vuelos,
    AVG(h.Precio_Ticket) AS Precio_Promedio_USD
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_CLASE    cl ON h.ID_Clase    = cl.ID_Clase
JOIN dbo.DIM_PASAJERO  p ON h.ID_Pasajero = p.ID_Pasajero
GROUP BY cl.Clase_Cabina, p.Genero
ORDER BY cl.Clase_Cabina, p.Genero;
GO

-- ============================================================
-- ANÁLISIS DE INGRESOS Y VENTAS
-- ============================================================

-- Ingresos totales y promedio por canal de venta
SELECT
    c.Canal,
    COUNT(*)                    AS Total_Reservas,
    SUM(h.Precio_Ticket)        AS Ingreso_Total_USD,
    AVG(h.Precio_Ticket)        AS Precio_Promedio_USD,
    MIN(h.Precio_Ticket)        AS Precio_Minimo,
    MAX(h.Precio_Ticket)        AS Precio_Maximo
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_CANAL c ON h.ID_Canal = c.ID_Canal
GROUP BY c.Canal
ORDER BY Ingreso_Total_USD DESC;
GO

-- Ingresos por método de pago
SELECT
    mp.Metodo_Pago,
    COUNT(*)             AS Total_Transacciones,
    SUM(h.Precio_Ticket) AS Ingreso_Total_USD,
    AVG(h.Precio_Ticket) AS Precio_Promedio_USD
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_METODO_PAGO mp ON h.ID_Metodo = mp.ID_Metodo
GROUP BY mp.Metodo_Pago
ORDER BY Ingreso_Total_USD DESC;
GO

-- Distribución de monedas usadas en compras
SELECT
    h.Moneda_Original,
    COUNT(*)             AS Total_Transacciones,
    SUM(h.Precio_Original) AS Total_Moneda_Original,
    SUM(h.Precio_Ticket)   AS Total_Equivalente_USD
FROM dbo.Hechos_Vuelo h
GROUP BY h.Moneda_Original
ORDER BY Total_Transacciones DESC;
GO

-- ============================================================
-- ANÁLISIS TEMPORAL
-- ============================================================

-- Vuelos por mes y año (tendencia temporal)
SELECT
    t.Año,
    t.Mes,
    t.Nombre_Mes,
    COUNT(*)             AS Total_Vuelos,
    SUM(h.Precio_Ticket) AS Ingreso_USD
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_TIEMPO t ON h.ID_Fecha_Salida = t.ID_Fecha
WHERE h.ID_Fecha_Salida IS NOT NULL
GROUP BY t.Año, t.Mes, t.Nombre_Mes
ORDER BY t.Año, t.Mes;
GO

-- Vuelos por trimestre
SELECT
    t.Año,
    t.Trimestre,
    COUNT(*)                    AS Total_Vuelos,
    SUM(h.Precio_Ticket)        AS Ingreso_Total_USD,
    AVG(CAST(h.Retraso AS FLOAT)) AS Retraso_Promedio_Min
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_TIEMPO t ON h.ID_Fecha_Salida = t.ID_Fecha
WHERE h.ID_Fecha_Salida IS NOT NULL
GROUP BY t.Año, t.Trimestre
ORDER BY t.Año, t.Trimestre;
GO

-- Comparativo fin de semana vs días laborales
SELECT
    CASE t.Es_Fin_Semana WHEN 1 THEN 'Fin de Semana' ELSE 'Día Laboral' END AS Tipo_Dia,
    COUNT(*)             AS Total_Vuelos,
    AVG(h.Precio_Ticket) AS Precio_Promedio_USD,
    AVG(CAST(h.Retraso AS FLOAT)) AS Retraso_Promedio_Min
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_TIEMPO t ON h.ID_Fecha_Salida = t.ID_Fecha
WHERE h.ID_Fecha_Salida IS NOT NULL
GROUP BY t.Es_Fin_Semana;
GO

-- ============================================================
-- ANÁLISIS DE EQUIPAJE
-- ============================================================

-- Promedio de maletas por clase de cabina
SELECT
    cl.Clase_Cabina,
    AVG(CAST(h.Total_Maletas     AS FLOAT)) AS Promedio_Maletas_Total,
    AVG(CAST(h.Maletas_Chequeadas AS FLOAT)) AS Promedio_Maletas_Chequeadas
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_CLASE cl ON h.ID_Clase = cl.ID_Clase
GROUP BY cl.Clase_Cabina
ORDER BY Promedio_Maletas_Total DESC;
GO

-- Pasajeros sin maletas vs con maletas por canal
SELECT
    c.Canal,
    SUM(CASE WHEN h.Total_Maletas = 0 THEN 1 ELSE 0 END) AS Sin_Maletas,
    SUM(CASE WHEN h.Total_Maletas > 0 THEN 1 ELSE 0 END) AS Con_Maletas,
    COUNT(*) AS Total
FROM dbo.Hechos_Vuelo h
JOIN dbo.DIM_CANAL c ON h.ID_Canal = c.ID_Canal
GROUP BY c.Canal
ORDER BY Total DESC;
GO