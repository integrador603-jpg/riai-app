import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "riai.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        username        TEXT UNIQUE NOT NULL,
        password_hash   TEXT NOT NULL,
        rol             TEXT NOT NULL DEFAULT 'operador',
        creado_en       TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS proveedores (
        codigo      TEXT PRIMARY KEY,
        nombre      TEXT NOT NULL,
        direccion   TEXT,
        contacto    TEXT,
        email       TEXT,
        telefono    TEXT
    );

    CREATE TABLE IF NOT EXISTS piezas (
        numero_pieza    TEXT PRIMARY KEY,
        descripcion     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS riai (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha           TEXT,
        idioma          TEXT DEFAULT 'es',
        unidad_long     TEXT DEFAULT 'mm',
        unidad_peso     TEXT DEFAULT 'kg',

        -- Proveedor
        proveedor_codigo    TEXT,
        proveedor_nombre    TEXT,
        proveedor_direccion TEXT,
        proveedor_contacto  TEXT,
        proveedor_email     TEXT,
        proveedor_telefono  TEXT,

        -- Pieza
        numero_pieza    TEXT,
        descripcion     TEXT,
        largo           REAL,
        ancho           REAL,
        alto            REAL,
        peso            REAL,
        moq             INTEGER,
        proyecto        TEXT,

        -- Embalaje
        emb_identico    INTEGER DEFAULT 0,
        colocacion      TEXT DEFAULT 'pallet',

        -- Embalaje primario
        p1_tipo         TEXT,
        p1_retornable   TEXT,
        p1_material     TEXT,
        p1_descripcion  TEXT,
        p1_largo        REAL,
        p1_ancho        REAL,
        p1_alto         REAL,
        p1_peso_emb     REAL,
        p1_capacidad    INTEGER,
        p1_peso_bruto   REAL,
        p1_cajas_capa   INTEGER,
        p1_capas        INTEGER,

        -- Embalaje secundario
        p2_tipo         TEXT,
        p2_retornable   TEXT,
        p2_material     TEXT,
        p2_descripcion  TEXT,
        p2_largo        REAL,
        p2_ancho        REAL,
        p2_alto         REAL,
        p2_peso_emb     REAL,
        p2_capacidad    INTEGER,
        p2_peso_bruto   REAL,

        -- Accesorios
        accesorios      TEXT,

        -- Imágenes (base64)
        img_caja        TEXT,
        img_abierta     TEXT,
        img_embalada    TEXT,
        img_paletizado  TEXT,

        -- Aprobaciones
        ap_elaborado_nombre TEXT,
        ap_elaborado_fecha  TEXT,
        ap_revisado_nombre  TEXT,
        ap_revisado_fecha   TEXT,
        ap_aprobado_nombre  TEXT,
        ap_aprobado_fecha   TEXT,

        estado          TEXT DEFAULT 'Borrador',
        creado_en       TEXT DEFAULT (datetime('now','localtime')),
        actualizado_en  TEXT DEFAULT (datetime('now','localtime'))
    );
    """)

    # Datos de ejemplo
    c.execute("SELECT COUNT(*) FROM proveedores")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO proveedores VALUES (?,?,?,?,?,?)", [
            ("AGN001","Agromaq S.A.","Av. Industria 1200, Córdoba","Juan Pérez","jperez@agromaq.com.ar","+54 351 400-1234"),
            ("MET002","Metales del Centro S.R.L.","Ruta 9 Km 12, Villa María","Laura Gómez","lgomez@metalesc.com.ar","+54 353 422-5678"),
            ("PLT003","Plásticos Tecno S.A.","Parque Industrial Oeste, Córdoba","Mario Silva","msilva@plasticoste.com.ar","+54 351 480-9012"),
            ("HID004","Hidráulica Córdoba S.A.","Av. Fuerza Aérea 3500, Córdoba","Ana Torres","atorres@hidraulicacba.com.ar","+54 351 460-3456"),
        ])

    c.execute("SELECT COUNT(*) FROM piezas")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO piezas VALUES (?,?)", [
            ("84567890","BRACKET SOPORTE MOTOR"),
            ("47891234","TUBO HIDRAULICO RETORNO"),
            ("63210987","PALANCA CAMBIOS COMPLETA"),
            ("29876543","SELLO GOMA 45MM"),
            ("11234567","FILTRO ACEITE TRANSMISION"),
        ])

    conn.commit()
    conn.close()
