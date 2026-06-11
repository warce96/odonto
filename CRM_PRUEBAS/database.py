"""database.py — Capa SQLite unificada (FinanGest)"""
import os, sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data", "gestor.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn; conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
            nombre TEXT, rol TEXT DEFAULT 'operador',
            creado TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, cedula TEXT NOT NULL DEFAULT '',
            telefono TEXT DEFAULT '', email TEXT DEFAULT '',
            direccion TEXT DEFAULT '', barrio TEXT DEFAULT '',
            referencia TEXT DEFAULT '', observacion TEXT DEFAULT '',
            margen_pago REAL DEFAULT 0, limite_credito REAL DEFAULT 0,
            fecha TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL, monto REAL NOT NULL,
            interes REAL NOT NULL, plazo INTEGER NOT NULL,
            cuota REAL, vencimiento TEXT, total REAL, ganancia REAL,
            fecha TEXT DEFAULT (date('now')),
            estado TEXT DEFAULT 'ACTIVO',
            cuotas_pagadas INTEGER DEFAULT 0,
            tuvo_mora TEXT DEFAULT 'NO',
            dias_mora INTEGER DEFAULT 0,
            mora_acumulada REAL DEFAULT 0,
            fecha_refin TEXT DEFAULT '', ref_id TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS refinanciaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL, deuda REAL NOT NULL,
            costo_admin REAL DEFAULT 0, interes REAL NOT NULL,
            plazo INTEGER NOT NULL, cuota REAL,
            ganancia REAL, total REAL, vencimiento TEXT,
            fecha TEXT DEFAULT (date('now')),
            observacion TEXT DEFAULT '',
            origen_tipo TEXT DEFAULT '', origen_id TEXT DEFAULT '',
            origen_descripcion TEXT DEFAULT '',
            cuotas_pagadas_origen INTEGER DEFAULT 0,
            tuvo_mora_origen TEXT DEFAULT 'NO',
            dias_mora_origen INTEGER DEFAULT 0,
            mora_acumulada_origen REAL DEFAULT 0,
            estado TEXT DEFAULT 'ACTIVO',
            cuotas_pagadas INTEGER DEFAULT 0,
            tuvo_mora TEXT DEFAULT 'NO',
            dias_mora INTEGER DEFAULT 0,
            mora_acumulada REAL DEFAULT 0,
            fecha_refin TEXT DEFAULT '', ref_id TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL, producto TEXT NOT NULL,
            precio REAL NOT NULL, fecha TEXT DEFAULT (date('now')),
            estado TEXT DEFAULT 'ACTIVO',
            pagado REAL DEFAULT 0,
            interes REAL DEFAULT 0,
            plazo INTEGER DEFAULT 1,
            cuota REAL DEFAULT 0,
            total REAL DEFAULT 0,
            fecha_refin TEXT DEFAULT '', ref_id TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS cheques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL, monto REAL NOT NULL,
            descuento REAL NOT NULL, neto REAL,
            fecha TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS cobros (
            id TEXT PRIMARY KEY,
            fecha_pago TEXT NOT NULL, tipo TEXT NOT NULL,
            operacion_id INTEGER NOT NULL, nro_cuota INTEGER NOT NULL,
            cliente TEXT NOT NULL, monto REAL NOT NULL,
            vencimiento TEXT DEFAULT '',
            estado TEXT DEFAULT 'PAGADO',
            fecha_anulacion TEXT DEFAULT '',
            motivo_anulacion TEXT DEFAULT '',
            referencia TEXT DEFAULT '',
            medio_pago TEXT DEFAULT 'Efectivo'
        );
        """)
        # Migrate existing ventas table if needed
        for col, definition in [
            ("interes", "REAL DEFAULT 0"),
            ("plazo",   "INTEGER DEFAULT 1"),
            ("cuota",   "REAL DEFAULT 0"),
            ("total",   "REAL DEFAULT 0"),
        ]:
            try:
                db.execute(f"ALTER TABLE ventas ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists

# ── Usuarios ──────────────────────────────────────────────
def crear_usuario_inicial():
    from werkzeug.security import generate_password_hash
    with get_db() as db:
        if not db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            db.execute("INSERT INTO usuarios (username,password,nombre,rol) VALUES (?,?,?,?)",
                       ("admin", generate_password_hash("admin123"), "Administrador", "admin"))

def get_usuario(username):
    with get_db() as db:
        return db.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()

def get_todos_usuarios():
    with get_db() as db:
        return db.execute("SELECT id,username,nombre,rol,creado FROM usuarios ORDER BY id").fetchall()

def crear_usuario(username, pw_hash, nombre, rol="operador"):
    with get_db() as db:
        db.execute("INSERT INTO usuarios (username,password,nombre,rol) VALUES (?,?,?,?)",
                   (username, pw_hash, nombre, rol))

def eliminar_usuario(uid):
    with get_db() as db:
        db.execute("DELETE FROM usuarios WHERE id=?", (uid,))

# ── Clientes ──────────────────────────────────────────────
def get_clientes():
    with get_db() as db:
        return db.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()

def get_cliente_por_nombre(nombre):
    with get_db() as db:
        return db.execute("SELECT * FROM clientes WHERE lower(nombre)=lower(?)", (nombre,)).fetchone()

def insertar_cliente(nombre, cedula, telefono="", email="", direccion="",
                     barrio="", referencia="", observacion="",
                     margen_pago=0, limite_credito=0):
    with get_db() as db:
        db.execute("""INSERT INTO clientes
            (nombre,cedula,telefono,email,direccion,barrio,referencia,observacion,margen_pago,limite_credito)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (nombre,cedula,telefono,email,direccion,barrio,referencia,observacion,margen_pago,limite_credito))

def insertar_cliente_si_no_existe(nombre):
    if not get_cliente_por_nombre(nombre):
        with get_db() as db:
            db.execute("INSERT INTO clientes (nombre,cedula) VALUES (?,?)", (nombre,"—"))

def eliminar_cliente(cid):
    with get_db() as db:
        db.execute("DELETE FROM clientes WHERE id=?", (cid,))

# ── Préstamos ─────────────────────────────────────────────
def get_prestamos():
    with get_db() as db:
        return db.execute("SELECT * FROM prestamos ORDER BY id DESC").fetchall()

def get_prestamo(pid):
    with get_db() as db:
        return db.execute("SELECT * FROM prestamos WHERE id=?", (pid,)).fetchone()

def insertar_prestamo(cliente, monto, interes, plazo, cuota, vencimiento, total, ganancia, fecha=None):
    from utils.fechas import hoy as _h
    with get_db() as db:
        cur = db.execute("""INSERT INTO prestamos
            (cliente,monto,interes,plazo,cuota,vencimiento,total,ganancia,fecha)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (cliente,monto,interes,plazo,cuota,vencimiento,total,ganancia,fecha or _h()))
        return cur.lastrowid

def actualizar_cuotas_prestamo(pid, cuotas_pagadas, estado):
    with get_db() as db:
        db.execute("UPDATE prestamos SET cuotas_pagadas=?, estado=? WHERE id=?",
                   (cuotas_pagadas, estado, pid))

def marcar_prestamo_refinanciado(pid, ref_id, cuotas_pagadas, tuvo_mora, dias_mora, mora_acumulada):
    from utils.fechas import hoy as _h
    with get_db() as db:
        db.execute("""UPDATE prestamos SET estado='REFINANCIADO',
            cuotas_pagadas=?,tuvo_mora=?,dias_mora=?,mora_acumulada=?,fecha_refin=?,ref_id=?
            WHERE id=?""", (cuotas_pagadas,tuvo_mora,dias_mora,mora_acumulada,_h(),ref_id,pid))

def eliminar_prestamo(pid):
    with get_db() as db:
        db.execute("DELETE FROM cobros WHERE tipo='prestamo' AND operacion_id=?", (pid,))
        db.execute("DELETE FROM prestamos WHERE id=?", (pid,))

# ── Refinanciaciones ──────────────────────────────────────
def get_refinanciaciones():
    with get_db() as db:
        return db.execute("SELECT * FROM refinanciaciones ORDER BY id DESC").fetchall()

def get_refinanciacion(rid):
    with get_db() as db:
        return db.execute("SELECT * FROM refinanciaciones WHERE id=?", (rid,)).fetchone()

def insertar_refinanciacion(cliente, deuda, costo_admin, interes, plazo, cuota,
                             ganancia, total, vencimiento, fecha, observacion,
                             origen_tipo, origen_id, origen_descripcion,
                             cp_origen, tm_origen, dm_origen, ma_origen):
    with get_db() as db:
        cur = db.execute("""INSERT INTO refinanciaciones
            (cliente,deuda,costo_admin,interes,plazo,cuota,ganancia,total,
             vencimiento,fecha,observacion,origen_tipo,origen_id,origen_descripcion,
             cuotas_pagadas_origen,tuvo_mora_origen,dias_mora_origen,mora_acumulada_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cliente,deuda,costo_admin,interes,plazo,cuota,ganancia,total,
             vencimiento,fecha,observacion,origen_tipo,origen_id,origen_descripcion,
             cp_origen,tm_origen,dm_origen,ma_origen))
        return cur.lastrowid

def actualizar_cuotas_refinanciacion(rid, cuotas_pagadas, estado):
    with get_db() as db:
        db.execute("UPDATE refinanciaciones SET cuotas_pagadas=?, estado=? WHERE id=?",
                   (cuotas_pagadas, estado, rid))

def marcar_refinanciacion_refinanciada(rid, ref_id, cuotas_pagadas, tuvo_mora, dias_mora, mora_acumulada):
    from utils.fechas import hoy as _h
    with get_db() as db:
        db.execute("""UPDATE refinanciaciones SET estado='REFINANCIADO',
            cuotas_pagadas=?,tuvo_mora=?,dias_mora=?,mora_acumulada=?,fecha_refin=?,ref_id=?
            WHERE id=?""", (cuotas_pagadas,tuvo_mora,dias_mora,mora_acumulada,_h(),ref_id,rid))

def eliminar_refinanciacion(rid):
    with get_db() as db:
        db.execute("DELETE FROM cobros WHERE tipo='refinanciacion' AND operacion_id=?", (rid,))
        db.execute("DELETE FROM refinanciaciones WHERE id=?", (rid,))

# ── Ventas ────────────────────────────────────────────────
def get_ventas():
    with get_db() as db:
        return db.execute("SELECT * FROM ventas ORDER BY id DESC").fetchall()

def get_venta(vid):
    with get_db() as db:
        return db.execute("SELECT * FROM ventas WHERE id=?", (vid,)).fetchone()

def insertar_venta(cliente, producto, precio, fecha=None,
                   interes=0.0, plazo=1, cuota=0.0, total=0.0):
    from utils.fechas import hoy as _h
    if not total:
        total = precio * (1 + float(interes or 0) / 100) if plazo and int(plazo) > 1 else precio
    if not cuota:
        cuota = float(total) / int(plazo) if plazo and int(plazo) > 0 else float(total)
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO ventas
               (cliente,producto,precio,fecha,interes,plazo,cuota,total)
               VALUES (?,?,?,?,?,?,?,?)""",
            (cliente, producto, precio, fecha or _h(),
             float(interes or 0), int(plazo or 1),
             round(float(cuota), 2), round(float(total), 2)))
        return cur.lastrowid

def actualizar_venta_pagado(vid, pagado, estado):
    with get_db() as db:
        db.execute("UPDATE ventas SET pagado=?, estado=? WHERE id=?", (pagado,estado,vid))

def marcar_venta_refinanciada(vid, ref_id, pagado):
    from utils.fechas import hoy as _h
    with get_db() as db:
        db.execute("UPDATE ventas SET estado='REFINANCIADO',pagado=?,fecha_refin=?,ref_id=? WHERE id=?",
                   (pagado,_h(),ref_id,vid))

def eliminar_venta(vid):
    with get_db() as db:
        db.execute("DELETE FROM cobros WHERE tipo='venta' AND operacion_id=?", (vid,))
        db.execute("DELETE FROM ventas WHERE id=?", (vid,))

# ── Cheques ───────────────────────────────────────────────
def get_cheques():
    with get_db() as db:
        return db.execute("SELECT * FROM cheques ORDER BY id DESC").fetchall()

def insertar_cheque(cliente, monto, descuento, neto):
    with get_db() as db:
        db.execute("INSERT INTO cheques (cliente,monto,descuento,neto) VALUES (?,?,?,?)",
                   (cliente,monto,descuento,neto))

def eliminar_cheque(cid):
    with get_db() as db:
        db.execute("DELETE FROM cheques WHERE id=?", (cid,))

# ── Cobros ────────────────────────────────────────────────
def siguiente_id_cobro():
    with get_db() as db:
        row = db.execute("SELECT id FROM cobros ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            return "P000001"
        try:
            n = int("".join(c for c in row["id"] if c.isdigit()))
            return f"P{n+1:06d}"
        except Exception:
            return "P000001"

def get_cobros_operacion(tipo, operacion_id, solo_activos=False):
    with get_db() as db:
        q = "SELECT * FROM cobros WHERE tipo=? AND operacion_id=?"
        if solo_activos:
            q += " AND estado='PAGADO'"
        q += " ORDER BY nro_cuota"
        return db.execute(q, (tipo, operacion_id)).fetchall()

def get_cobro_cuota(tipo, operacion_id, nro_cuota):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM cobros WHERE tipo=? AND operacion_id=? AND nro_cuota=? AND estado='PAGADO'",
            (tipo, operacion_id, nro_cuota)).fetchone()

def get_cobro_por_id(cobro_id):
    with get_db() as db:
        return db.execute("SELECT * FROM cobros WHERE id=?", (cobro_id,)).fetchone()

def registrar_cobro(cobro_id, fecha_pago, tipo, operacion_id, nro_cuota,
                    cliente, monto, vencimiento, referencia, medio_pago):
    with get_db() as db:
        db.execute("""INSERT INTO cobros
            (id,fecha_pago,tipo,operacion_id,nro_cuota,cliente,monto,
             vencimiento,estado,referencia,medio_pago)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (cobro_id,fecha_pago,tipo,operacion_id,nro_cuota,
             cliente,monto,vencimiento,"PAGADO",referencia,medio_pago))

def anular_cobro(cobro_id, motivo=""):
    from utils.fechas import hoy as _h
    with get_db() as db:
        db.execute("""UPDATE cobros SET estado='ANULADO',fecha_anulacion=?,motivo_anulacion=?
            WHERE id=?""", (_h(), motivo or "Anulado", cobro_id))

def resumen_cobros_operacion(tipo, operacion_id):
    cobros = get_cobros_operacion(tipo, operacion_id, solo_activos=True)
    return len(cobros), sum(float(c["monto"]) for c in cobros)

# ── Stats ─────────────────────────────────────────────────
def get_stats():
    with get_db() as db:
        nc   = db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        np   = db.execute("SELECT COUNT(*) FROM prestamos").fetchone()[0]
        nr   = db.execute("SELECT COUNT(*) FROM refinanciaciones").fetchone()[0]
        nv   = db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0]
        cap  = db.execute("SELECT COALESCE(SUM(monto),0) FROM prestamos").fetchone()[0]
        capr = db.execute("SELECT COALESCE(SUM(deuda),0) FROM refinanciaciones").fetchone()[0]
        up   = db.execute("SELECT COALESCE(SUM(ganancia),0) FROM prestamos").fetchone()[0]
        ur   = db.execute("SELECT COALESCE(SUM(ganancia),0) FROM refinanciaciones").fetchone()[0]
        venc = db.execute("SELECT COUNT(*) FROM prestamos WHERE vencimiento<date('now') AND estado='ACTIVO'").fetchone()[0]
        uc   = db.execute("SELECT * FROM clientes ORDER BY id DESC LIMIT 5").fetchall()
        up5  = db.execute("SELECT * FROM prestamos ORDER BY id DESC LIMIT 5").fetchall()
        ur5  = db.execute("SELECT * FROM refinanciaciones ORDER BY id DESC LIMIT 5").fetchall()
    return dict(n_clientes=nc,n_prestamos=np,n_refinanciaciones=nr,n_ventas=nv,
                cap_prestamos=cap,cap_refin=capr,util_prestamos=up,util_refin=ur,
                util_total=up+ur,vencidos=venc,
                ult_clientes=uc,ult_prestamos=up5,ult_refin=ur5)
