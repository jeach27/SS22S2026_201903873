"""
============================================================
 PRÁCTICA 1 - Seminario de Sistemas 2
 ETL: Extracción, Transformación y Carga de datos de vuelos
 Fuentes : Dataset_1.csv (vuelos) y Dataset_2.csv (pasajeros)
 Destino : SQL Server - base de datos VuelosBI
============================================================
"""

import pandas as pd
import pyodbc
import logging
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

# Rutas de los archivos fuente
RUTA_DATASET1 = ".\Dataset\Dataset 1.csv"
RUTA_DATASET2 = ".\Dataset\Dataset 2.csv" 

CONEXION_SQL = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=VuelosBI;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# Ruta donde se guardará el log de errores
RUTA_LOG = "etl_log.txt"


# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(RUTA_LOG, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ============================================================
# CATÁLOGOS DE REFERENCIA
# Valores esperados que usaremos para validar y enriquecer
# ============================================================

# Aeropuertos conocidos - código IATA → (nombre, país)
AEROPUERTOS = {
    "GUA": ("Aeropuerto Internacional La Aurora",             "Guatemala"),
    "MEX": ("Aeropuerto Internacional Benito Juárez",         "México"),
    "MIA": ("Miami International Airport",                    "Estados Unidos"),
    "JFK": ("John F. Kennedy International Airport",          "Estados Unidos"),
    "LAX": ("Los Angeles International Airport",              "Estados Unidos"),
    "BOG": ("Aeropuerto Internacional El Dorado",             "Colombia"),
    "LIM": ("Aeropuerto Internacional Jorge Chávez",          "Perú"),
    "PTY": ("Aeropuerto Internacional de Tocumen",            "Panamá"),
    "SAP": ("Aeropuerto Internacional Ramón Villeda Morales", "Honduras"),
    "SJO": ("Aeropuerto Internacional Juan Santamaría",       "Costa Rica"),
    "SAL": ("Aeropuerto Internacional Monseñor Óscar Romero", "El Salvador"),
    "HAV": ("Aeropuerto Internacional José Martí",            "Cuba"),
    "CUN": ("Aeropuerto Internacional de Cancún",             "México"),
    "BCN": ("Aeropuerto de Barcelona-El Prat",                "España"),
    "MAD": ("Aeropuerto Adolfo Suárez Madrid-Barajas",        "España"),
}

# Normalización de género: cualquier variante → M / F / X
NORMALIZACION_GENERO = {
    "m": "M", "masculino": "M", "male": "M",
    "f": "F", "femenino": "F", "female": "F",
    "x": "X", "otro": "X", "other": "X", "o": "X",
    "n": "X", "nonbinary": "X", "no binario": "X",  
}


# ============================================================
# FASE 1: EXTRACCIÓN
# ============================================================

def extraer_datos():
    """
    Lee Dataset_1 (vuelos) y Dataset_2 (pasajeros) desde disco.
    Devuelve dos DataFrames crudos o lanza excepción si falla.
    """
    log.info("=" * 60)
    log.info("FASE 1: EXTRACCIÓN")
    log.info("=" * 60)

    # -- Dataset 1: separado por coma --
    log.info(f"Leyendo {RUTA_DATASET1}...")
    try:
        df_vuelos = pd.read_csv(
            RUTA_DATASET1,
            encoding="utf-8-sig",   # maneja el BOM que trae el archivo
            dtype=str,              # leer todo como texto; transformamos luego
            keep_default_na=False,  # no convertir "" a NaN automáticamente
        )
        log.info(f"  Dataset_1 leído: {len(df_vuelos):,} filas, {len(df_vuelos.columns)} columnas")
    except FileNotFoundError:
        log.error(f"No se encontró el archivo {RUTA_DATASET1}. Verifica la ruta.")
        raise

    # -- Dataset 2: separado por punto y coma --
    log.info(f"Leyendo {RUTA_DATASET2}...")
    try:
        df_pasajeros = pd.read_csv(
            RUTA_DATASET2,
            encoding="utf-8-sig",
            sep=";",
            dtype=str,
            keep_default_na=False,
        )
        log.info(f"  Dataset_2 leído: {len(df_pasajeros):,} filas, {len(df_pasajeros.columns)} columnas")
    except FileNotFoundError:
        log.error(f"No se encontró el archivo {RUTA_DATASET2}. Verifica la ruta.")
        raise

    # Verificar que ambos tienen la misma cantidad de filas (join por índice)
    if len(df_vuelos) != len(df_pasajeros):
        log.warning(
            f"Los datasets tienen distinto número de filas: "
            f"{len(df_vuelos)} vs {len(df_pasajeros)}. "
            f"Se usará el mínimo para el join."
        )
        filas = min(len(df_vuelos), len(df_pasajeros))
        df_vuelos   = df_vuelos.iloc[:filas].copy()
        df_pasajeros = df_pasajeros.iloc[:filas].copy()

    log.info("Extracción completada exitosamente.\n")
    return df_vuelos, df_pasajeros


# ============================================================
# FASE 2: TRANSFORMACIÓN
# ============================================================

def parsear_fecha(valor: str) -> datetime | None:
    """
    Intenta convertir un string a datetime probando varios formatos.
    Retorna None si el valor está vacío o ningún formato aplica.
    """
    valor = valor.strip()
    if not valor:
        return None

    formatos = [
        "%d/%m/%Y %H:%M",       # 20/01/2024 10:14  (formato principal)
        "%-d/%m/%Y %H:%M",      # 4/10/2025 05:08   (día sin cero)
        "%m-%d-%Y %I:%M %p",    # 03-15-2025 01:58 PM (formato americano con AM/PM)
        "%d/%m/%Y",             # solo fecha sin hora
        "%Y-%m-%d %H:%M:%S",    # formato ISO
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            continue

    log.warning(f"  No se pudo parsear la fecha: '{valor}'")
    return None


def normalizar_genero(valor: str) -> str:
    clave = valor.strip().lower().replace("-", "").replace("_", "")
    resultado = NORMALIZACION_GENERO.get(clave, "X")
    return resultado[0]  


def convertir_precio(valor: str) -> float | None:
    """
    Convierte strings de precio a float.
    Maneja tanto '77.60' como '77,60' (coma decimal).
    """
    valor = valor.strip().replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def transformar_vuelos(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y estandariza el DataFrame de vuelos (Dataset_1).
    """
    log.info("Transformando Dataset_1 (vuelos)...")
    df = df_raw.copy()
    errores = 0

    # -- Limpiar espacios en blanco de todos los campos de texto --
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # -- Aeropuertos: normalizar a mayúsculas --
    for col in ["origin_airport", "destination_airport"]:
        antes = df[col].str.upper()
        invalidos = ~antes.isin(AEROPUERTOS.keys())
        if invalidos.any():
            log.warning(
                f"  {invalidos.sum()} aeropuertos desconocidos en '{col}': "
                f"{df.loc[invalidos, col].unique().tolist()}"
            )
            errores += invalidos.sum()
        df[col] = antes

    # -- Fechas de salida y llegada --
    log.info("  Parseando fechas de vuelo...")
    df["departure_dt"] = df["departure_datetime"].apply(parsear_fecha)
    df["arrival_dt"]   = df["arrival_datetime"].apply(parsear_fecha)

    sin_salida = df["departure_dt"].isna() & (df["departure_datetime"] != "")
    if sin_salida.any():
        log.warning(f"  {sin_salida.sum()} fechas de salida no pudieron parsearse.")
        errores += sin_salida.sum()

    # -- Duración y retraso: convertir a entero, None si vacío --
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    df["delay_min"]    = pd.to_numeric(df["delay_min"],    errors="coerce")

    # Validar que duración no sea negativa
    dur_negativa = df["duration_min"] < 0
    if dur_negativa.any():
        log.warning(f"  {dur_negativa.sum()} registros con duración negativa → se anulan.")
        df.loc[dur_negativa, "duration_min"] = None
        errores += dur_negativa.sum()

    # -- Estado del vuelo --
    estados_validos = {"ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"}
    estados_invalidos = ~df["status"].isin(estados_validos)
    if estados_invalidos.any():
        log.warning(
            f"  {estados_invalidos.sum()} estados inválidos: "
            f"{df.loc[estados_invalidos, 'status'].unique().tolist()} → se marcan como 'ON_TIME'"
        )
        df.loc[estados_invalidos, "status"] = "ON_TIME"
        errores += estados_invalidos.sum()

    # Vuelos cancelados sin datos de llegada/duración/retraso es esperado
    cancelados = df["status"] == "CANCELLED"
    log.info(f"  Vuelos CANCELLED (sin llegada/duración): {cancelados.sum()}")

    log.info(f"  Transformación vuelos completada. Errores/advertencias: {errores}")
    return df


def transformar_pasajeros(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y estandariza el DataFrame de pasajeros (Dataset_2).
    """
    log.info("Transformando Dataset_2 (pasajeros)...")
    df = df_raw.copy()
    errores = 0

    # -- Limpiar espacios --
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # -- Género: normalizar variantes --
    df["genero_normalizado"] = df["passenger_gender"].apply(normalizar_genero)
    generos_distintos = df["passenger_gender"].nunique()
    log.info(f"  Género normalizado: {generos_distintos} variantes → M/F/X")

    # -- Edad: convertir a entero, tratar 0 como nulo --
    df["passenger_age"] = pd.to_numeric(df["passenger_age"], errors="coerce")
    edades_cero = df["passenger_age"] == 0
    if edades_cero.any():
        log.warning(f"  {edades_cero.sum()} edades con valor 0 → se convierten a NULL")
        df.loc[edades_cero, "passenger_age"] = None
        errores += edades_cero.sum()

    edades_invalidas = df["passenger_age"] > 120
    if edades_invalidas.any():
        log.warning(f"  {edades_invalidas.sum()} edades mayores a 120 → se convierten a NULL")
        df.loc[edades_invalidas, "passenger_age"] = None
        errores += edades_invalidas.sum()

    # -- Nacionalidad: vacíos → None --
    df["passenger_nationality"] = df["passenger_nationality"].replace("", None)
    nulos_nat = df["passenger_nationality"].isna().sum()
    if nulos_nat:
        log.warning(f"  {nulos_nat} registros sin nacionalidad → quedarán como NULL")

    # -- Canal de venta: vacíos → 'DESCONOCIDO' --
    canales_vacios = df["sales_channel"] == ""
    if canales_vacios.any():
        log.warning(f"  {canales_vacios.sum()} registros sin canal de venta → 'DESCONOCIDO'")
        df.loc[canales_vacios, "sales_channel"] = "DESCONOCIDO"
        errores += canales_vacios.sum()

    # -- Precio: manejar coma decimal --
    df["precio_original"] = df["ticket_price"].apply(convertir_precio)
    precios_nulos = df["precio_original"].isna()
    if precios_nulos.any():
        log.warning(f"  {precios_nulos.sum()} precios no pudieron convertirse → se usará ticket_price_usd_est")
        errores += precios_nulos.sum()

    df["precio_usd"] = pd.to_numeric(df["ticket_price_usd_est"], errors="coerce")
    # Si precio_original es nulo, usar el estimado en USD como fallback
    df.loc[precios_nulos, "precio_original"] = df.loc[precios_nulos, "precio_usd"]

    # Precios negativos o cero son inválidos
    precios_invalidos = df["precio_usd"] <= 0
    if precios_invalidos.any():
        log.warning(f"  {precios_invalidos.sum()} precios USD inválidos (≤0)")
        errores += precios_invalidos.sum()

    # -- Fecha de reserva --
    log.info("  Parseando fechas de reserva...")
    df["booking_dt"] = df["booking_datetime"].apply(parsear_fecha)
    sin_reserva = df["booking_dt"].isna()
    if sin_reserva.any():
        log.warning(f"  {sin_reserva.sum()} fechas de reserva no pudieron parsearse.")
        errores += sin_reserva.sum()

    # -- Maletas: convertir a entero --
    df["bags_total"]   = pd.to_numeric(df["bags_total"],   errors="coerce").fillna(0).astype(int)
    df["bags_checked"] = pd.to_numeric(df["bags_checked"], errors="coerce").fillna(0).astype(int)

    log.info(f"  Transformación pasajeros completada. Errores/advertencias: {errores}")
    return df


# ============================================================
# CONSTRUCCIÓN DE DIMENSIONES
# Extraer los valores únicos de los datasets para poblar
# cada tabla de dimensión antes de insertar la tabla de hechos
# ============================================================

def construir_dimensiones(df_vuelos: pd.DataFrame, df_pasajeros: pd.DataFrame) -> dict:
    """
    Construye los DataFrames de cada dimensión a partir de los datos limpios.
    Devuelve un diccionario con todos los DataFrames de dimensión.
    """
    log.info("Construyendo dimensiones...")

    dims = {}

    # DIM_AEROLINEA
    dims["aerolinea"] = (
        df_vuelos[["airline_code", "airline_name"]]
        .drop_duplicates(subset="airline_code")
        .rename(columns={"airline_code": "Codigo", "airline_name": "Nombre"})
        .reset_index(drop=True)
    )

    # DIM_AEROPUERTO - de los datos + el catálogo enriquecido
    aeropuertos_raw = pd.Series(
        df_vuelos["origin_airport"].tolist() + df_vuelos["destination_airport"].tolist()
    ).unique()
    dims["aeropuerto"] = pd.DataFrame([
        {"Codigo": cod, "Nombre": AEROPUERTOS[cod][0], "Pais": AEROPUERTOS[cod][1]}
        for cod in aeropuertos_raw if cod in AEROPUERTOS
    ])

    # DIM_CANAL
    canales = df_pasajeros["sales_channel"].unique()
    dims["canal"] = pd.DataFrame({"Canal": canales})

    # DIM_METODO_PAGO
    metodos = df_pasajeros["payment_method"].unique()
    dims["metodo_pago"] = pd.DataFrame({"Metodo_Pago": metodos})

    # DIM_AERONAVE
    aeronaves = df_vuelos["aircraft_type"].unique()
    dims["aeronave"] = pd.DataFrame({"Tipo_Aeronave": aeronaves})

    # DIM_CLASE
    clases = df_vuelos["cabin_class"].unique()
    dims["clase"] = pd.DataFrame({"Clase_Cabina": clases})

    # DIM_ESTADO_VUELO
    estados = df_vuelos["status"].unique()
    dims["estado_vuelo"] = pd.DataFrame({"Estado": estados})

    # DIM_PASAJERO
    dims["pasajero"] = df_pasajeros[[
        "passenger_id", "genero_normalizado", "passenger_age", "passenger_nationality"
    ]].rename(columns={
        "passenger_id":           "Passenger_UUID",
        "genero_normalizado":     "Genero",
        "passenger_age":          "Edad",
        "passenger_nationality":  "Nacionalidad",
    }).copy()

    # DIM_TIEMPO - generar todas las fechas únicas presentes en los datos
    todas_las_fechas = set()
    for col_dt in ["departure_dt", "arrival_dt"]:
        for dt in df_vuelos[col_dt].dropna():
            todas_las_fechas.add(dt.date())
    for dt in df_pasajeros["booking_dt"].dropna():
        todas_las_fechas.add(dt.date())

    nombres_mes = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    filas_tiempo = []
    for fecha in sorted(todas_las_fechas):
        filas_tiempo.append({
            "ID_Fecha":       int(fecha.strftime("%Y%m%d")),
            "Fecha_Completa": fecha,
            "Año":            fecha.year,
            "Mes":            fecha.month,
            "Nombre_Mes":     nombres_mes[fecha.month],
            "Dia":            fecha.day,
            "Dia_Semana":     fecha.isoweekday(),   # 1=Lunes, 7=Domingo
            "Trimestre":      (fecha.month - 1) // 3 + 1,
            "Es_Fin_Semana":  1 if fecha.isoweekday() >= 6 else 0,
        })
    dims["tiempo"] = pd.DataFrame(filas_tiempo)

    for nombre, df in dims.items():
        log.info(f"  DIM_{nombre.upper()}: {len(df)} registros")

    return dims


# ============================================================
# FASE 3: CARGA
# ============================================================

def obtener_conexion() -> pyodbc.Connection:
    """Crea y devuelve una conexión a SQL Server."""
    try:
        conn = pyodbc.connect(CONEXION_SQL, timeout=10)
        log.info("Conexión a SQL Server establecida.")
        return conn
    except pyodbc.Error as e:
        log.error(f"No se pudo conectar a SQL Server: {e}")
        raise


def cargar_dimension(cursor, tabla: str, columnas: list, filas: list, clave: str = None):
    """
    Inserta filas en una tabla de dimensión.
    Si 'clave' se especifica, usa INSERT IF NOT EXISTS para no duplicar.
    Retorna un dict {valor_clave: id_generado}.
    """
    mapa_id = {}

    for fila in filas:
        valores = [fila.get(c) for c in columnas]

        if clave:
            # Verificar si ya existe para no insertar duplicados
            cursor.execute(
                f"SELECT ID_{tabla.replace('DIM_','')} FROM dbo.{tabla} WHERE {clave} = ?",
                fila[clave]
            )
            row = cursor.fetchone()
            if row:
                mapa_id[fila[clave]] = row[0]
                continue

        placeholders = ", ".join(["?"] * len(columnas))
        cols_str     = ", ".join(columnas)
        cursor.execute(
            f"INSERT INTO dbo.{tabla} ({cols_str}) OUTPUT INSERTED.ID_{tabla.replace('DIM_','')} VALUES ({placeholders})",
            valores
        )
        nuevo_id = cursor.fetchone()[0]
        if clave:
            mapa_id[fila[clave]] = nuevo_id

    return mapa_id


def cargar_datos(dims: dict, df_vuelos: pd.DataFrame, df_pasajeros: pd.DataFrame):
    """
    Carga todas las dimensiones y la tabla de hechos en SQL Server.
    Usa una transacción por tabla para poder hacer rollback ante errores.
    """
    log.info("=" * 60)
    log.info("FASE 3: CARGA")
    log.info("=" * 60)

    conn = obtener_conexion()
    conn.autocommit = False
    cursor = conn.cursor()
    cursor.fast_executemany = True  # mejora el rendimiento de inserción masiva

    try:
        # ---- DIM_TIEMPO ----
        log.info("Cargando DIM_TIEMPO...")
        filas_tiempo = dims["tiempo"].to_dict("records")
        for fila in filas_tiempo:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_TIEMPO WHERE ID_Fecha = ?)
                INSERT INTO dbo.DIM_TIEMPO
                    (ID_Fecha, Fecha_Completa, Año, Mes, Nombre_Mes, Dia, Dia_Semana, Trimestre, Es_Fin_Semana)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, fila["ID_Fecha"],
                 fila["ID_Fecha"], fila["Fecha_Completa"], fila["Año"], fila["Mes"],
                 fila["Nombre_Mes"], fila["Dia"], fila["Dia_Semana"], fila["Trimestre"],
                 fila["Es_Fin_Semana"])
        conn.commit()
        log.info(f"  DIM_TIEMPO: {len(filas_tiempo)} registros cargados.")

        # ---- DIM_AEROLINEA ----
        log.info("Cargando DIM_AEROLINEA...")
        map_aerolinea = {}
        for _, row in dims["aerolinea"].iterrows():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_AEROLINEA WHERE Codigo = ?)
                INSERT INTO dbo.DIM_AEROLINEA (Codigo, Nombre) VALUES (?,?)
            """, row["Codigo"], row["Codigo"], row["Nombre"])
            cursor.execute("SELECT ID_Aerolinea FROM dbo.DIM_AEROLINEA WHERE Codigo = ?", row["Codigo"])
            map_aerolinea[row["Codigo"]] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_AEROLINEA: {len(map_aerolinea)} registros.")

        # ---- DIM_AEROPUERTO ----
        log.info("Cargando DIM_AEROPUERTO...")
        map_aeropuerto = {}
        for _, row in dims["aeropuerto"].iterrows():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_AEROPUERTO WHERE Codigo = ?)
                INSERT INTO dbo.DIM_AEROPUERTO (Codigo, Nombre, Pais) VALUES (?,?,?)
            """, row["Codigo"], row["Codigo"], row["Nombre"], row["Pais"])
            cursor.execute("SELECT ID_Aeropuerto FROM dbo.DIM_AEROPUERTO WHERE Codigo = ?", row["Codigo"])
            map_aeropuerto[row["Codigo"]] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_AEROPUERTO: {len(map_aeropuerto)} registros.")

        # ---- DIM_CANAL ----
        log.info("Cargando DIM_CANAL...")
        map_canal = {}
        for canal in dims["canal"]["Canal"].unique():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_CANAL WHERE Canal = ?)
                INSERT INTO dbo.DIM_CANAL (Canal) VALUES (?)
            """, canal, canal)
            cursor.execute("SELECT ID_Canal FROM dbo.DIM_CANAL WHERE Canal = ?", canal)
            map_canal[canal] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_CANAL: {len(map_canal)} registros.")

        # ---- DIM_METODO_PAGO ----
        log.info("Cargando DIM_METODO_PAGO...")
        map_metodo = {}
        for metodo in dims["metodo_pago"]["Metodo_Pago"].unique():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_METODO_PAGO WHERE Metodo_Pago = ?)
                INSERT INTO dbo.DIM_METODO_PAGO (Metodo_Pago) VALUES (?)
            """, metodo, metodo)
            cursor.execute("SELECT ID_Metodo FROM dbo.DIM_METODO_PAGO WHERE Metodo_Pago = ?", metodo)
            map_metodo[metodo] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_METODO_PAGO: {len(map_metodo)} registros.")

        # ---- DIM_AERONAVE ----
        log.info("Cargando DIM_AERONAVE...")
        map_aeronave = {}
        for aeronave in dims["aeronave"]["Tipo_Aeronave"].unique():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_AERONAVE WHERE Tipo_Aeronave = ?)
                INSERT INTO dbo.DIM_AERONAVE (Tipo_Aeronave) VALUES (?)
            """, aeronave, aeronave)
            cursor.execute("SELECT ID_Aeronave FROM dbo.DIM_AERONAVE WHERE Tipo_Aeronave = ?", aeronave)
            map_aeronave[aeronave] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_AERONAVE: {len(map_aeronave)} registros.")

        # ---- DIM_CLASE ----
        log.info("Cargando DIM_CLASE...")
        map_clase = {}
        for clase in dims["clase"]["Clase_Cabina"].unique():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_CLASE WHERE Clase_Cabina = ?)
                INSERT INTO dbo.DIM_CLASE (Clase_Cabina) VALUES (?)
            """, clase, clase)
            cursor.execute("SELECT ID_Clase FROM dbo.DIM_CLASE WHERE Clase_Cabina = ?", clase)
            map_clase[clase] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_CLASE: {len(map_clase)} registros.")

        # ---- DIM_ESTADO_VUELO ----
        log.info("Cargando DIM_ESTADO_VUELO...")
        map_estado = {}
        for estado in dims["estado_vuelo"]["Estado"].unique():
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_ESTADO_VUELO WHERE Estado = ?)
                INSERT INTO dbo.DIM_ESTADO_VUELO (Estado) VALUES (?)
            """, estado, estado)
            cursor.execute("SELECT ID_Estado_Vuelo FROM dbo.DIM_ESTADO_VUELO WHERE Estado = ?", estado)
            map_estado[estado] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_ESTADO_VUELO: {len(map_estado)} registros.")

        # ---- DIM_PASAJERO ----
        log.info("Cargando DIM_PASAJERO...")
        map_pasajero = {}
        for _, row in dims["pasajero"].iterrows():
            edad = None if pd.isna(row["Edad"]) else int(row["Edad"])
            nac  = None if pd.isna(row["Nacionalidad"]) or row["Nacionalidad"] == "" else row["Nacionalidad"]
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.DIM_PASAJERO WHERE Passenger_UUID = ?)
                INSERT INTO dbo.DIM_PASAJERO (Passenger_UUID, Genero, Edad, Nacionalidad)
                VALUES (?,?,?,?)
            """, row["Passenger_UUID"],
                 row["Passenger_UUID"], row["Genero"], edad, nac)
            cursor.execute("SELECT ID_Pasajero FROM dbo.DIM_PASAJERO WHERE Passenger_UUID = ?", row["Passenger_UUID"])
            map_pasajero[row["Passenger_UUID"]] = cursor.fetchone()[0]
        conn.commit()
        log.info(f"  DIM_PASAJERO: {len(map_pasajero)} registros.")

        # ---- HECHOS_VUELO ----
        log.info("Cargando Hechos_Vuelo (puede tardar unos segundos)...")

        def fecha_a_id(dt) -> int | None:
            """Convierte un datetime a ID de fecha (YYYYMMDD) o None."""
            if dt is None or pd.isna(dt):
                return None
            if isinstance(dt, datetime):
                return int(dt.strftime("%Y%m%d"))
            return None

        filas_hechos = []
        omitidos = 0

        for i in range(len(df_vuelos)):
            fila_v = df_vuelos.iloc[i]
            fila_p = df_pasajeros.iloc[i]

            # Obtener IDs de dimensiones - si alguno crítico falta, omitir la fila
            id_aerolinea  = map_aerolinea.get(fila_v["airline_code"])
            id_origen     = map_aeropuerto.get(fila_v["origin_airport"])
            id_destino    = map_aeropuerto.get(fila_v["destination_airport"])
            id_pasajero   = map_pasajero.get(fila_p["passenger_id"])
            id_canal      = map_canal.get(fila_p["sales_channel"])
            id_metodo     = map_metodo.get(fila_p["payment_method"])
            id_aeronave   = map_aeronave.get(fila_v["aircraft_type"])
            id_clase      = map_clase.get(fila_v["cabin_class"])
            id_estado     = map_estado.get(fila_v["status"])
            id_f_reserva  = fecha_a_id(fila_p["booking_dt"])

            # Validar que los campos obligatorios existen
            campos_criticos = {
                "ID_Aerolinea":  id_aerolinea,
                "ID_Origen":     id_origen,
                "ID_Destino":    id_destino,
                "ID_Pasajero":   id_pasajero,
                "ID_Canal":      id_canal,
                "ID_Metodo":     id_metodo,
                "ID_Aeronave":   id_aeronave,
                "ID_Clase":      id_clase,
                "ID_Estado":     id_estado,
                "ID_F_Reserva":  id_f_reserva,
            }
            faltantes = [k for k, v in campos_criticos.items() if v is None]
            if faltantes:
                log.warning(f"  Fila {i}: omitida por campos nulos → {faltantes}")
                omitidos += 1
                continue

            filas_hechos.append((
                id_aerolinea,
                id_pasajero,
                id_origen,
                id_destino,
                fecha_a_id(fila_v["departure_dt"]),     # puede ser NULL (cancelado)
                fecha_a_id(fila_v["arrival_dt"]),        # puede ser NULL (cancelado)
                id_f_reserva,
                id_canal,
                id_metodo,
                id_aeronave,
                id_clase,
                id_estado,
                float(fila_p["precio_usd"])    if pd.notna(fila_p["precio_usd"])     else 0.0,
                fila_p["currency"]             if fila_p["currency"]                 else "USD",
                float(fila_p["precio_original"]) if pd.notna(fila_p["precio_original"]) else 0.0,
                int(fila_p["bags_total"]),
                int(fila_p["bags_checked"]),
                int(fila_v["duration_min"])    if pd.notna(fila_v["duration_min"])   else None,
                int(fila_v["delay_min"])       if pd.notna(fila_v["delay_min"])      else None,
                1,  # Cantidad_Vuelo siempre 1
            ))

        # Inserción masiva de la tabla de hechos
        sql_hechos = """
            INSERT INTO dbo.Hechos_Vuelo (
                ID_Aerolinea, ID_Pasajero,
                ID_Aeropuerto_Origen, ID_Aeropuerto_Destino,
                ID_Fecha_Salida, ID_Fecha_Llegada, ID_Fecha_Reserva,
                ID_Canal, ID_Metodo, ID_Aeronave, ID_Clase, ID_Estado_Vuelo,
                Precio_Ticket, Moneda_Original, Precio_Original,
                Total_Maletas, Maletas_Chequeadas,
                Duracion, Retraso, Cantidad_Vuelo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        cursor.executemany(sql_hechos, filas_hechos)
        conn.commit()

        log.info(f"  Hechos_Vuelo: {len(filas_hechos):,} registros insertados.")
        if omitidos:
            log.warning(f"  {omitidos} filas omitidas por datos críticos faltantes.")

    except Exception as e:
        conn.rollback()
        log.error(f"Error durante la carga. Se hizo rollback. Detalle: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        log.info("Conexión cerrada.")


# ============================================================
# PUNTO DE ENTRADA PRINCIPAL
# ============================================================

def main():
    inicio = datetime.now()
    log.info("=" * 60)
    log.info("  INICIO DEL PROCESO ETL - VuelosBI")
    log.info(f"  Fecha y hora: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    try:
        # FASE 1: Extracción
        df_vuelos_raw, df_pasajeros_raw = extraer_datos()

        # FASE 2: Transformación
        log.info("=" * 60)
        log.info("FASE 2: TRANSFORMACIÓN")
        log.info("=" * 60)
        df_vuelos    = transformar_vuelos(df_vuelos_raw)
        df_pasajeros = transformar_pasajeros(df_pasajeros_raw)

        # Construir dimensiones
        dims = construir_dimensiones(df_vuelos, df_pasajeros)

        # FASE 3: Carga
        cargar_datos(dims, df_vuelos, df_pasajeros)

        fin = datetime.now()
        duracion = (fin - inicio).seconds
        log.info("=" * 60)
        log.info(f"  ETL COMPLETADO EXITOSAMENTE")
        log.info(f"  Duración total: {duracion} segundos")
        log.info(f"  Log guardado en: {RUTA_LOG}")
        log.info("=" * 60)

    except Exception as e:
        log.error(f"El proceso ETL falló: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()