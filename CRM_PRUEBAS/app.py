"""
app.py — FinanGest · Sistema de gestión financiera
Fusión completa: SQLite + login + riesgo + cobros + tickets + catálogo
"""
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, flash, redirect, render_template,
                   request, session, url_for, send_from_directory)
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from catalogo_data import CATALOGO, CATEGORIAS, LINEAS, MARCAS
from utils.calculos import (calcular_cuota, calcular_descuento_cheque,
                             calcular_ganancia_credito, calcular_total_credito)
from utils.fechas import fecha_vencimiento, hoy, sumar_meses

APP_NAME     = "FinanGest"
APP_TAGLINE  = "Sistema de gestión financiera"
APP_INITIALS = "FG"

app = Flask(__name__)
app.secret_key = "finangest-2025-secret"

# ── JSON encoder: convierte sqlite3.Row a dict automáticamente ──
import json as _json
import sqlite3 as _sqlite3

class _RowEncoder(_json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, _sqlite3.Row):
            return dict(obj)
        return super().default(obj)

class _RowProvider(app.json_provider_class):
    def dumps(self, obj, **kw):
        kw.setdefault('cls', _RowEncoder)
        return _json.dumps(obj, **kw)

app.json_provider_class = _RowProvider
app.json = _RowProvider(app)

with app.app_context():
    db.init_db()
    db.crear_usuario_inicial()

# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if session.get("rol") != "admin":
            flash("Acceso restringido a administradores.", "danger")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return login_required(d)

# ─────────────────────────────────────────────────────────
# Formatos
# ─────────────────────────────────────────────────────────
def moneda(v):
    try: return f"Gs. {float(v or 0):,.0f}".replace(",", ".")
    except: return "Gs. 0"

def numero(v):
    d = "".join(c for c in str(v or "") if c.isdigit())
    if not d: return "—"
    return f"{int(d):,}".replace(",", ".")

def porcentaje(v):
    try: return f"{float(v or 0):.2f}%"
    except: return "0.00%"

def _float(v, default=0.0):
    try:
        t = str(v or "").strip().replace(" ", "")
        if not t: return default
        # Remove currency prefix if present
        t = t.replace("Gs.", "").replace("gs.", "").strip()
        # Multiple dots = thousands separators (e.g. "1.500.000")
        if t.count(".") > 1:
            return float(t.replace(".", ""))
        # Single dot: check if it's a thousands separator (3 digits after dot, all digits)
        if t.count(".") == 1:
            parts = t.split(".")
            if len(parts[1]) == 3 and parts[0].isdigit() and parts[1].isdigit():
                return float(t.replace(".", ""))  # "500.000" → 500000
        return float(t)
    except: return default

def _int(v, default=0):
    try: return int(_float(v, default))
    except: return default

# ─────────────────────────────────────────────────────────
# Lógica de riesgo / operaciones pendientes
# ─────────────────────────────────────────────────────────
def deuda_prestamo(p):
    """Retorna (saldo, pagado, total) para un préstamo SQLite Row."""
    total   = _float(p["total"])
    cuota   = _float(p["cuota"])
    pagadas = _int(p["cuotas_pagadas"])
    mora    = _float(p["mora_acumulada"])
    pagado  = min(total, cuota * max(0, pagadas))
    saldo   = max(0.0, total - pagado) + mora
    return round(saldo, 2), round(pagado, 2), round(total + mora, 2)

def deuda_refinanciacion(r):
    total   = _float(r["total"])
    cuota   = _float(r["cuota"])
    pagadas = _int(r["cuotas_pagadas"])
    mora    = _float(r["mora_acumulada"])
    pagado  = min(total, cuota * max(0, pagadas))
    saldo   = max(0.0, total - pagado) + mora
    return round(saldo, 2), round(pagado, 2), round(total + mora, 2)

def deuda_venta(v):
    # Use total (with interest) if available, otherwise precio
    try:
        total = _float(v["total"]) if v["total"] else _float(v["precio"])
    except Exception:
        total = _float(v["precio"])
    if not total:
        total = _float(v["precio"])
    pagado = _float(v["pagado"])
    saldo  = max(0.0, total - pagado)
    return round(saldo, 2), round(min(pagado, total), 2), round(total, 2)

def _row_to_dict_safe(v):
    """Convierte sqlite3.Row a dict si es necesario, o devuelve el valor tal cual."""
    try:
        return dict(v)
    except Exception:
        return v

def operaciones_pendientes_cliente(nombre_cliente=None):
    """Lista operaciones activas con saldo > 0 para un cliente o todos."""
    ops = []
    nombre_norm = (nombre_cliente or "").strip().lower()

    for p in db.get_prestamos():
        if p["estado"] in ("REFINANCIADO", "CANCELADO"):
            continue
        if nombre_norm and nombre_norm != p["cliente"].strip().lower():
            continue
        saldo, pagado, compromiso = deuda_prestamo(p)
        if saldo <= 0:
            continue
        ops.append({
            "id": f"prestamo:{p['id']}",
            "tipo": "prestamo", "tipo_label": "Préstamo",
            "indice": int(p["id"]), "cliente": str(p["cliente"] or ""),
            "descripcion": f"Préstamo · Capital {moneda(p['monto'])}",
            "detalle": f"Interés {p['interes']:g}% · {p['plazo']} meses · cuota {moneda(p['cuota'])}",
            "saldo": float(saldo), "saldo_fmt": moneda(saldo),
            "pagado": float(pagado), "pagado_fmt": moneda(pagado),
            "cuota": float(_float(p["cuota"])), "total_original": float(_float(p["total"])),
            "fecha": str(p["fecha"] or ""), "vencimiento": str(p["vencimiento"] or ""),
            "estado": str(p["estado"] or ""),
        })

    for r in db.get_refinanciaciones():
        if r["estado"] in ("REFINANCIADO", "CANCELADO"):
            continue
        if nombre_norm and nombre_norm != r["cliente"].strip().lower():
            continue
        saldo, pagado, compromiso = deuda_refinanciacion(r)
        if saldo <= 0:
            continue
        ops.append({
            "id": f"refinanciacion:{r['id']}",
            "tipo": "refinanciacion", "tipo_label": "Refinanciación",
            "indice": int(r["id"]), "cliente": str(r["cliente"] or ""),
            "descripcion": f"Refinanciación · {r['origen_descripcion'] or 'Deuda anterior'}",
            "detalle": f"Interés {r['interes']:g}% · {r['plazo']} meses · cuota {moneda(r['cuota'])}",
            "saldo": float(saldo), "saldo_fmt": moneda(saldo),
            "pagado": float(pagado), "pagado_fmt": moneda(pagado),
            "cuota": float(_float(r["cuota"])), "total_original": float(_float(r["total"])),
            "fecha": str(r["fecha"] or ""), "vencimiento": str(r["vencimiento"] or ""),
            "estado": str(r["estado"] or ""),
        })

    for v in db.get_ventas():
        if v["estado"] in ("REFINANCIADO", "CANCELADO"):
            continue
        if nombre_norm and nombre_norm != v["cliente"].strip().lower():
            continue
        saldo, pagado, _ = deuda_venta(v)
        if saldo <= 0:
            continue
        ops.append({
            "id": f"venta:{v['id']}",
            "tipo": "venta", "tipo_label": "Venta",
            "indice": int(v["id"]), "cliente": str(v["cliente"] or ""),
            "descripcion": f"Venta · {v['producto']}",
            "detalle": f"Precio {moneda(v['precio'])} · pagado {moneda(v['pagado'])}",
            "saldo": float(saldo), "saldo_fmt": moneda(saldo),
            "pagado": float(pagado), "pagado_fmt": moneda(pagado),
            "cuota": float(_float(v["cuota"]) if "cuota" in v.keys() and v["cuota"] else _float(v["precio"])),
            "total_original": float(deuda_venta(v)[2]),
            "fecha": str(v["fecha"] or ""), "vencimiento": "",
            "estado": str(v["estado"] or ""),
        })

    return ops

def perfil_riesgo(nombre_cliente):
    c = db.get_cliente_por_nombre(nombre_cliente)
    if not c:
        return None
    ops = operaciones_pendientes_cliente(nombre_cliente)
    riesgo    = sum(o["saldo"] for o in ops)
    pagado    = sum(o["pagado"] for o in ops)
    compromiso= sum(o["total_original"] for o in ops)
    pct_pago  = round((pagado / compromiso) * 100, 2) if compromiso > 0 else 100.0
    margen    = _float(c["margen_pago"])
    pago_nec  = max(0.0, (compromiso * margen / 100) - pagado) if compromiso > 0 else 0.0
    margen_ok = pct_pago >= margen or compromiso == 0
    limite    = _float(c["limite_credito"])
    excede    = bool(limite and riesgo > limite)
    return {
        "riesgo": riesgo, "riesgo_fmt": moneda(riesgo),
        "pagado": pagado, "pagado_fmt": moneda(pagado),
        "porcentaje_pagado": pct_pago, "porcentaje_pagado_fmt": porcentaje(pct_pago),
        "margen": margen, "margen_fmt": porcentaje(margen),
        "pago_necesario": pago_nec, "pago_necesario_fmt": moneda(pago_nec),
        "habilitado": margen_ok and not excede,
        "excede_limite": excede,
        "limite_credito": limite, "limite_credito_fmt": moneda(limite),
    }

def alertas_vencimiento(dias=7):
    hoy_d  = datetime.strptime(hoy(), "%Y-%m-%d").date()
    limite = hoy_d + timedelta(days=dias)
    result = []
    for p in db.get_prestamos():
        if p["estado"] in ("REFINANCIADO", "CANCELADO"):
            continue
        pagadas = _int(p["cuotas_pagadas"])
        plazo   = _int(p["plazo"])
        if pagadas >= plazo:
            continue
        prox = sumar_meses(p["fecha"] or hoy(), pagadas + 1)
        try:
            prox_d = datetime.strptime(prox, "%Y-%m-%d").date()
        except Exception:
            continue
        if prox_d > limite:
            continue
        saldo, _, _ = deuda_prestamo(p)
        dias_r = (prox_d - hoy_d).days
        result.append({
            "cliente": p["cliente"], "tipo": "Préstamo",
            "vencimiento": prox, "dias": dias_r,
            "estado": "Vencido" if dias_r < 0 else "Por vencer",
            "saldo_fmt": moneda(saldo),
        })
    for r in db.get_refinanciaciones():
        if r["estado"] in ("REFINANCIADO", "CANCELADO"):
            continue
        pagadas = _int(r["cuotas_pagadas"])
        plazo   = _int(r["plazo"])
        if pagadas >= plazo:
            continue
        prox = sumar_meses(r["fecha"] or hoy(), pagadas + 1)
        try:
            prox_d = datetime.strptime(prox, "%Y-%m-%d").date()
        except Exception:
            continue
        if prox_d > limite:
            continue
        saldo, _, _ = deuda_refinanciacion(r)
        dias_r = (prox_d - hoy_d).days
        result.append({
            "cliente": r["cliente"], "tipo": "Refinanciación",
            "vencimiento": prox, "dias": dias_r,
            "estado": "Vencido" if dias_r < 0 else "Por vencer",
            "saldo_fmt": moneda(saldo),
        })
    return sorted(result, key=lambda a: a["dias"])

def clientes_con_perfil():
    result = []
    for c in db.get_clientes():
        perfil = perfil_riesgo(c["nombre"]) or {
            "riesgo": 0, "riesgo_fmt": moneda(0),
            "pagado": 0, "pagado_fmt": moneda(0),
            "porcentaje_pagado_fmt": "0.00%",
            "margen_fmt": porcentaje(c["margen_pago"]),
            "pago_necesario_fmt": moneda(0),
            "habilitado": True, "excede_limite": False,
            "limite_credito_fmt": moneda(c["limite_credito"]),
        }
        result.append({
            "cliente": c, "perfil": perfil,
            "alertas": [a for a in alertas_vencimiento() if a["cliente"].lower() == c["nombre"].lower()],
        })
    return result

# ─────────────────────────────────────────────────────────
# Cuotero de operación (para cuotas.html)
# ─────────────────────────────────────────────────────────
def detalle_operacion(tipo, oid):
    if tipo == "prestamo":
        p = db.get_prestamo(oid)
        if not p: return None
        return {
            "tipo": "prestamo", "tipo_label": "Préstamo",
            "indice": p["id"], "id": f"prestamo:{p['id']}",
            "cliente": p["cliente"],
            "descripcion": f"Préstamo de {moneda(p['monto'])}",
            "fecha_inicio": p["fecha"] or hoy(),
            "plazo": max(1, _int(p["plazo"], 1)),
            "cuota": _float(p["cuota"]),
            "total": _float(p["total"]),
            "estado": p["estado"],
        }
    if tipo == "refinanciacion":
        r = db.get_refinanciacion(oid)
        if not r: return None
        return {
            "tipo": "refinanciacion", "tipo_label": "Refinanciación",
            "indice": r["id"], "id": f"refinanciacion:{r['id']}",
            "cliente": r["cliente"],
            "descripcion": r["origen_descripcion"] or "Refinanciación",
            "fecha_inicio": r["fecha"] or hoy(),
            "plazo": max(1, _int(r["plazo"], 1)),
            "cuota": _float(r["cuota"]),
            "total": _float(r["total"]),
            "estado": r["estado"],
        }
    if tipo == "venta":
        v = db.get_venta(oid)
        if not v: return None
        plazo_v = _int(v["plazo"]) if "plazo" in v.keys() and v["plazo"] else 1
        cuota_v = _float(v["cuota"]) if "cuota" in v.keys() and v["cuota"] else _float(v["precio"])
        total_v = _float(v["total"]) if "total" in v.keys() and v["total"] else _float(v["precio"])
        if total_v == 0: total_v = _float(v["precio"])
        if cuota_v == 0: cuota_v = total_v / plazo_v if plazo_v > 0 else total_v
        return {
            "tipo": "venta", "tipo_label": "Venta",
            "indice": v["id"], "id": f"venta:{v['id']}",
            "cliente": v["cliente"],
            "descripcion": v["producto"],
            "fecha_inicio": v["fecha"] or hoy(),
            "plazo": max(1, plazo_v),
            "cuota": cuota_v,
            "total": total_v,
            "estado": v["estado"],
        }
    return None

def cuotero_operacion(tipo, oid):
    det = detalle_operacion(tipo, oid)
    if not det: return None, []
    plazo = det["plazo"]
    total = det["total"]
    cuota_base = det["cuota"] if det["cuota"] > 0 else (total / plazo if plazo else total)
    filas = []
    for nro in range(1, plazo + 1):
        monto = cuota_base
        if nro == plazo and tipo in ("prestamo", "refinanciacion"):
            monto = max(0.0, total - cuota_base * (plazo - 1))
        cobro = db.get_cobro_cuota(tipo, oid, nro)
        # Para ventas con plazo > 1, también usar sumar_meses
        if tipo == "venta" and det["plazo"] > 1:
            venc = sumar_meses(det["fecha_inicio"], nro)
        elif tipo in ("prestamo", "refinanciacion"):
            venc = sumar_meses(det["fecha_inicio"], nro)
        else:
            venc = det["fecha_inicio"]
        filas.append({
            "nro": nro, "vencimiento": venc,
            "monto": monto, "monto_fmt": moneda(monto),
            "pagado": bool(cobro),
            "pago_id": cobro["id"] if cobro else "",
            "fecha_pago": cobro["fecha_pago"] if cobro else "",
        })
    return det, filas

def actualizar_estado_por_cobros(tipo, oid):
    cantidad, _ = db.resumen_cobros_operacion(tipo, oid)
    if tipo == "prestamo":
        p = db.get_prestamo(oid)
        if p and p["estado"] != "REFINANCIADO":
            plazo = _int(p["plazo"])
            estado = "CANCELADO" if cantidad >= plazo else "ACTIVO"
            db.actualizar_cuotas_prestamo(oid, cantidad, estado)
    elif tipo == "refinanciacion":
        r = db.get_refinanciacion(oid)
        if r and r["estado"] != "REFINANCIADO":
            plazo = _int(r["plazo"])
            estado = "CANCELADO" if cantidad >= plazo else "ACTIVO"
            db.actualizar_cuotas_refinanciacion(oid, cantidad, estado)
    elif tipo == "venta":
        v = db.get_venta(oid)
        if v and v["estado"] != "REFINANCIADO":
            _, total_cobrado = db.resumen_cobros_operacion(tipo, oid)
            total = _float(v["precio"])
            estado = "CANCELADO" if total_cobrado >= total and total > 0 else "ACTIVO"
            db.actualizar_venta_pagado(oid, total_cobrado, estado)

# ─────────────────────────────────────────────────────────
# Context processor
# ─────────────────────────────────────────────────────────
@app.context_processor
def ctx():
    return {
        "moneda": moneda, "numero": numero, "porcentaje": porcentaje, "hoy": hoy,
        "APP_NAME": APP_NAME, "APP_TAGLINE": APP_TAGLINE, "APP_INITIALS": APP_INITIALS,
        "current_user": session.get("username", ""),
        "current_rol": session.get("rol", ""),
        "session": session,
    }

# ─────────────────────────────────────────────────────────
# Auth routes
# ─────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        u = db.get_usuario(request.form.get("username", "").strip())
        if u and check_password_hash(u["password"], request.form.get("password", "")):
            session.update(user_id=u["id"], username=u["username"],
                           nombre=u["nombre"] or u["username"], rol=u["rol"])
            return redirect(url_for("index"))
        error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    s = db.get_stats()
    stats = {
        "clientes": s["n_clientes"],
        "prestamos": s["n_prestamos"],
        "refinanciaciones": s["n_refinanciaciones"],
        "ventas": s["n_ventas"],
        "total_prestamos": moneda(s["cap_prestamos"]),
        "total_refinanciado": moneda(s["cap_refin"]),
        "utilidad_prestamos": moneda(s["util_prestamos"]),
        "utilidad_refinanciaciones": moneda(s["util_refin"]),
        "utilidad_total": moneda(s["util_total"]),
        "vencidos": s["vencidos"],
        "saldo_pendiente": moneda(sum(o["saldo"] for o in operaciones_pendientes_cliente())),
        "pendientes": len(operaciones_pendientes_cliente()),
        "alertas_vencimiento": len(alertas_vencimiento()),
    }
    return render_template("index.html",
        stats=stats,
        ultimos_clientes=s["ult_clientes"],
        ultimos_prestamos=s["ult_prestamos"],
        ultimas_refinanciaciones=s["ult_refin"],
        operaciones_pendientes=operaciones_pendientes_cliente()[:8],
        alertas=alertas_vencimiento()[:10],
        clientes_riesgo=clientes_con_perfil()[:8],
    )

# ─────────────────────────────────────────────────────────
# Clientes
# ─────────────────────────────────────────────────────────
@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        cedula = request.form.get("cedula", "").strip()
        if not nombre or not cedula:
            flash("Nombre y cédula son obligatorios.", "danger")
        else:
            db.insertar_cliente(
                nombre, cedula,
                request.form.get("telefono", ""),
                request.form.get("correo", ""),
                request.form.get("direccion", ""),
                request.form.get("barrio", ""),
                request.form.get("referencia", ""),
                request.form.get("observacion", ""),
                _float(request.form.get("margen_pago", 0)),
                _float(request.form.get("limite_credito", 0)),
            )
            flash("Cliente registrado.", "success")
        return redirect(url_for("clientes"))
    return render_template("clientes.html",
                           clientes=clientes_con_perfil())

@app.route("/clientes/eliminar/<int:cid>", methods=["POST"])
@login_required
def eliminar_cliente(cid):
    db.eliminar_cliente(cid)
    flash("Cliente eliminado.", "success")
    return redirect(url_for("clientes"))

@app.route("/clientes/rapido", methods=["POST"])
@login_required
def crear_cliente_rapido():
    siguiente = request.form.get("next") or url_for("clientes")
    nombre = request.form.get("nombre", "").strip()
    cedula = request.form.get("cedula", "").strip()
    if not nombre or not cedula:
        flash("Nombre y cédula son obligatorios.", "danger")
    else:
        db.insertar_cliente(
            nombre, cedula,
            request.form.get("telefono", ""),
            margen_pago=_float(request.form.get("margen_pago", 0)),
            limite_credito=_float(request.form.get("limite_credito", 0)),
        )
        flash(f"Cliente '{nombre}' creado.", "success")
    return redirect(siguiente)

# ─────────────────────────────────────────────────────────
# Préstamos
# ─────────────────────────────────────────────────────────
@app.route("/prestamos", methods=["GET", "POST"])
@login_required
def prestamos():
    clientes_lista = [dict(c) for c in db.get_clientes()]
    if request.method == "POST":
        try:
            cliente   = request.form.get("cliente", "").strip()
            monto     = _float(request.form.get("monto", 0))
            interes   = _float(request.form.get("interes", 0))
            plazo     = _int(request.form.get("plazo", 0))
            fecha_op  = request.form.get("fecha_operacion", "").strip() or hoy()
            autorizar = request.form.get("autorizar_excepcion") == "SI"

            if not cliente or monto <= 0 or plazo <= 0:
                raise ValueError("Datos inválidos")

            perfil = perfil_riesgo(cliente)
            if perfil and not perfil["habilitado"] and not autorizar:
                flash(f"El cliente no cumple el margen mínimo. Debe pagar {perfil['pago_necesario_fmt']} más. Marcá excepción si hay autorización.", "danger")
                return redirect(url_for("prestamos"))

            cuota     = calcular_cuota(monto, interes, plazo)
            total     = calcular_total_credito(monto, interes)
            ganancia  = calcular_ganancia_credito(monto, interes)
            venc      = fecha_vencimiento(plazo, fecha_op)
            db.insertar_prestamo(cliente, monto, interes, plazo, cuota, venc, total, ganancia, fecha_op)
            db.insertar_cliente_si_no_existe(cliente)
            flash("Préstamo registrado correctamente.", "success")
        except ValueError as e:
            flash(f"Verifique los datos: {e}", "danger")
        return redirect(url_for("prestamos"))

    pends = operaciones_pendientes_cliente()
    return render_template("prestamos.html",
        prestamos=db.get_prestamos(),
        clientes=clientes_lista,
        pendientes=pends,
    )

@app.route("/prestamos/eliminar/<int:pid>", methods=["POST"])
@login_required
def eliminar_prestamo(pid):
    db.eliminar_prestamo(pid)
    flash("Préstamo eliminado.", "success")
    return redirect(url_for("prestamos"))

# ─────────────────────────────────────────────────────────
# Refinanciaciones
# ─────────────────────────────────────────────────────────
@app.route("/refinanciaciones", methods=["GET", "POST"])
@login_required
def refinanciaciones():
    clientes_lista = [dict(c) for c in db.get_clientes()]
    if request.method == "POST":
        try:
            cliente      = request.form.get("cliente", "").strip()
            operacion_id = request.form.get("operacion_id", "").strip()
            interes      = _float(request.form.get("interes", 0))
            plazo        = _int(request.form.get("plazo", 0))
            costo_admin  = _float(request.form.get("costo_admin", 0) or 0)
            observacion  = request.form.get("observacion", "").strip()
            cp_origen    = _int(request.form.get("cuotas_pagadas_origen", 0))
            tm_origen    = "SI" if request.form.get("tuvo_mora_origen") == "SI" else "NO"
            dm_origen    = _int(request.form.get("dias_mora_origen", 0))
            ma_origen    = _float(request.form.get("mora_acumulada_origen", 0) or 0)

            if not cliente:
                flash("Seleccione un cliente.", "danger")
                return redirect(url_for("refinanciaciones"))

            # Buscar la operación pendiente
            pends_cliente = operaciones_pendientes_cliente(cliente)
            op = None

            if operacion_id == "__TODA__":
                # Refinanciar toda la deuda acumulada del cliente
                deuda_total = sum(o["saldo"] for o in pends_cliente)
                op = {
                    "id": "__TODA__",
                    "tipo": "multiple",
                    "indice": 0,
                    "descripcion": f"Unificación de {len(pends_cliente)} operaciones",
                    "saldo": deuda_total,
                    "total_original": deuda_total,
                    "cuota": 0,
                }
                deuda_actual = max(0.0, deuda_total + ma_origen)
                # Marcar todas las operaciones pendientes como REFINANCIADAS
                for o in pends_cliente:
                    if o["tipo"] == "prestamo":
                        db.marcar_prestamo_refinanciado(o["indice"], "__TODA__", cp_origen, tm_origen, dm_origen, ma_origen)
                    elif o["tipo"] == "refinanciacion":
                        db.marcar_refinanciacion_refinanciada(o["indice"], "__TODA__", cp_origen, tm_origen, dm_origen, ma_origen)
                    elif o["tipo"] == "venta":
                        db.marcar_venta_refinanciada(o["indice"], "__TODA__", o["pagado"])
            else:
                if operacion_id:
                    for o in pends_cliente:
                        if o["id"] == operacion_id:
                            op = o
                            break

                if not op:
                    flash("Seleccione una operación pendiente del cliente.", "danger")
                    return redirect(url_for("refinanciaciones"))

                # Recalcular saldo con cuotas pagadas informadas
                tipo_op = op["tipo"]
                oid_op  = op["indice"]
                if tipo_op == "prestamo":
                    p = db.get_prestamo(oid_op)
                    total_op = _float(p["total"]) if p else op["total_original"]
                    cuota_op = _float(p["cuota"]) if p else op["cuota"]
                elif tipo_op == "refinanciacion":
                    r = db.get_refinanciacion(oid_op)
                    total_op = _float(r["total"]) if r else op["total_original"]
                    cuota_op = _float(r["cuota"]) if r else op["cuota"]
                else:
                    total_op = op["total_original"]
                    cuota_op = op["cuota"]

                deuda_actual = max(0.0, total_op - cuota_op * cp_origen) + ma_origen
            if deuda_actual <= 0 or plazo <= 0:
                raise ValueError("Deuda o plazo inválidos")

            base    = deuda_actual + costo_admin
            cuota   = calcular_cuota(base, interes, plazo)
            total   = calcular_total_credito(base, interes)
            ganancia= round(total - deuda_actual, 2)
            venc    = fecha_vencimiento(plazo)
            fecha_h = hoy()

            origen_tipo_final = op["tipo"] if operacion_id != "__TODA__" else "multiple"
            origen_desc_final = op["descripcion"] if operacion_id != "__TODA__" else f"Unificación de deudas del cliente"
            rid = db.insertar_refinanciacion(
                cliente, deuda_actual, costo_admin, interes, plazo, cuota,
                ganancia, total, venc, fecha_h, observacion,
                origen_tipo_final, operacion_id, origen_desc_final,
                cp_origen, tm_origen, dm_origen, ma_origen
            )

            # Marcar operación original como REFINANCIADA
            ref_id = f"refinanciacion:{rid}"
            if operacion_id != "__TODA__":
                tipo_op = op["tipo"]
                oid_op  = op["indice"]
                if tipo_op == "prestamo":
                    db.marcar_prestamo_refinanciado(oid_op, ref_id, cp_origen, tm_origen, dm_origen, ma_origen)
                elif tipo_op == "refinanciacion":
                    db.marcar_refinanciacion_refinanciada(oid_op, ref_id, cp_origen, tm_origen, dm_origen, ma_origen)
                elif tipo_op == "venta":
                    db.marcar_venta_refinanciada(oid_op, ref_id, op["pagado"])
            else:
                # Ya fueron marcadas arriba en el bloque __TODA__
                # Actualizar ref_id correcto en cada una
                for o in operaciones_pendientes_cliente.__wrapped__ if hasattr(operaciones_pendientes_cliente, '__wrapped__') else []:
                    pass  # already marked

            flash("Refinanciación registrada. La operación original quedó marcada como REFINANCIADO.", "success")
        except ValueError as e:
            flash(f"Verifique los datos: {e}", "danger")
        return redirect(url_for("refinanciaciones"))

    pends_r = operaciones_pendientes_cliente()
    return render_template("refinanciaciones.html",
        refinanciaciones=db.get_refinanciaciones(),
        clientes=clientes_lista,
        pendientes=pends_r,
    )

@app.route("/refinanciaciones/eliminar/<int:rid>", methods=["POST"])
@login_required
def eliminar_refinanciacion(rid):
    db.eliminar_refinanciacion(rid)
    flash("Refinanciación eliminada.", "success")
    return redirect(url_for("refinanciaciones"))

# ─────────────────────────────────────────────────────────
# Ventas
# ─────────────────────────────────────────────────────────
@app.route("/ventas", methods=["GET", "POST"])
@login_required
def ventas():
    clientes_lista = [dict(c) for c in db.get_clientes()]
    if request.method == "POST":
        cliente   = request.form.get("cliente", "").strip()
        # 'nombre_producto' viene del catálogo, 'producto' del formulario directo
        producto  = (request.form.get("nombre_producto") or request.form.get("producto", "")).strip()
        precio    = _float(request.form.get("precio", 0))
        interes   = _float(request.form.get("interes", 0) or 0)
        plazo     = _int(request.form.get("plazo", 0) or request.form.get("cuotas", 0) or 0)
        autorizar = request.form.get("autorizar_excepcion") == "SI"

        if not cliente or not producto or precio <= 0:
            flash("Cliente, producto y precio son obligatorios.", "danger")
            return redirect(url_for("ventas"))

        perfil = perfil_riesgo(cliente)
        if perfil and not perfil["habilitado"] and not autorizar:
            flash(f"El cliente no cumple el margen mínimo. Debe pagar {perfil['pago_necesario_fmt']} más. Marcá excepción si hay autorización.", "danger")
            return redirect(url_for("ventas"))

        total_venta = precio * (1 + interes / 100) if plazo > 1 and interes > 0 else precio
        cuota_venta = total_venta / plazo if plazo > 0 else total_venta
        db.insertar_venta(cliente, producto, precio,
                          interes=interes, plazo=max(1, plazo),
                          cuota=round(cuota_venta, 2), total=round(total_venta, 2))
        db.insertar_cliente_si_no_existe(cliente)
        flash("Venta registrada correctamente.", "success")
        return redirect(url_for("ventas"))

    pends_v = operaciones_pendientes_cliente()
    return render_template("ventas.html",
        ventas=db.get_ventas(),
        clientes=clientes_lista,
        pendientes=pends_v,
    )

@app.route("/ventas/eliminar/<int:vid>", methods=["POST"])
@login_required
def eliminar_venta(vid):
    db.eliminar_venta(vid)
    flash("Venta eliminada.", "success")
    return redirect(url_for("ventas"))

# ─────────────────────────────────────────────────────────
# Cheques
# ─────────────────────────────────────────────────────────
@app.route("/cheques", methods=["GET", "POST"])
@login_required
def cheques():
    clientes_lista = [dict(c) for c in db.get_clientes()]
    if request.method == "POST":
        try:
            cliente   = request.form.get("cliente", "").strip()
            monto     = _float(request.form.get("monto", 0))
            descuento = _float(request.form.get("porcentaje", 0))
            if not cliente or monto <= 0 or descuento < 0:
                raise ValueError
            neto = calcular_descuento_cheque(monto, descuento)
            db.insertar_cheque(cliente, monto, descuento, neto)
            flash("Cheque registrado.", "success")
        except ValueError:
            flash("Verifique los datos.", "danger")
        return redirect(url_for("cheques"))
    pends_ch = operaciones_pendientes_cliente()
    return render_template("cheques.html",
        cheques=db.get_cheques(),
        clientes=clientes_lista,
        pendientes=pends_ch,
    )

@app.route("/cheques/eliminar/<int:cid>", methods=["POST"])
@login_required
def eliminar_cheque(cid):
    db.eliminar_cheque(cid)
    flash("Cheque eliminado.", "success")
    return redirect(url_for("cheques"))

# ─────────────────────────────────────────────────────────
# Cuotas y cobros
# ─────────────────────────────────────────────────────────
@app.route("/cuotas/<tipo>/<int:oid>")
@login_required
def cuotas_operacion(tipo, oid):
    det, cuotas = cuotero_operacion(tipo, oid)
    if not det:
        flash("Operación no encontrada.", "danger")
        return redirect(url_for("index"))
    historico = db.get_cobros_operacion(tipo, oid, solo_activos=False)
    return render_template("cuotas.html",
        detalle=det, cuotas=cuotas, pagos_historicos=historico)

@app.route("/cuotas/<tipo>/<int:oid>/pagar/<int:nro>", methods=["POST"])
@login_required
def pagar_cuota(tipo, oid, nro):
    det, filas = cuotero_operacion(tipo, oid)
    if not det:
        flash("Operación no encontrada.", "danger")
        return redirect(url_for("index"))
    if det["estado"] in ("REFINANCIADO", "CANCELADO"):
        flash(f"No se puede cobrar una operación {det['estado']}.", "danger")
        return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))
    if db.get_cobro_cuota(tipo, oid, nro):
        flash("Esa cuota ya está pagada.", "danger")
        return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))

    fila = next((f for f in filas if f["nro"] == nro), None)
    if not fila:
        flash("Cuota no encontrada.", "danger")
        return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))

    cobro_id   = db.siguiente_id_cobro()
    medio_pago = request.form.get("medio_pago", "Efectivo") or "Efectivo"
    db.registrar_cobro(cobro_id, hoy(), tipo, oid, nro,
                       det["cliente"], fila["monto"], fila["vencimiento"],
                       det["id"], medio_pago)
    actualizar_estado_por_cobros(tipo, oid)
    flash("Pago registrado correctamente.", "success")

    if request.form.get("generar_ticket") == "SI":
        return redirect(url_for("ticket_pago", cobro_id=cobro_id))
    return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))

@app.route("/cuotas/<tipo>/<int:oid>/anular/<int:nro>", methods=["POST"])
@login_required
def anular_cuota(tipo, oid, nro):
    cobro = db.get_cobro_cuota(tipo, oid, nro)
    if not cobro:
        flash("No se encontró pago activo para anular.", "danger")
        return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))
    motivo = request.form.get("motivo", "Anulado por operador")
    db.anular_cobro(cobro["id"], motivo)
    actualizar_estado_por_cobros(tipo, oid)
    flash("Pago anulado correctamente.", "success")
    return redirect(url_for("cuotas_operacion", tipo=tipo, oid=oid))

# ─────────────────────────────────────────────────────────
# Ticket
# ─────────────────────────────────────────────────────────
@app.route("/ticket/<cobro_id>")
@login_required
def ticket_pago(cobro_id):
    cobro = db.get_cobro_por_id(cobro_id)
    if not cobro:
        flash("Ticket no encontrado.", "danger")
        return redirect(url_for("index"))

    tipo = cobro["tipo"]
    oid  = cobro["operacion_id"]
    det, filas = cuotero_operacion(tipo, oid)
    plazo = det["plazo"] if det else 1
    nro   = cobro["nro_cuota"]

    cobros_activos = db.get_cobros_operacion(tipo, oid, solo_activos=True)
    total_pagado   = sum(_float(c["monto"]) for c in cobros_activos)
    cuotas_pagadas = len(cobros_activos)
    total_op       = det["total"] if det else _float(cobro["monto"])
    saldo          = max(0.0, total_op - total_pagado)
    cuotas_pend    = max(0, plazo - cuotas_pagadas)

    prox_venc = "Operación cancelada" if cuotas_pend == 0 else "—"
    prox_cuota = "Última cuota" if cuotas_pend == 0 else "Pendiente"
    if det and filas:
        sig = next((f for f in filas if not f["pagado"]), None)
        if sig:
            prox_venc  = sig["vencimiento"]
            prox_cuota = f"Cuota {sig['nro']} de {plazo}"

    ticket = {
        "id": cobro["id"],
        "fecha": cobro["fecha_pago"],
        "fecha_emision": hoy(),
        "tipo": det["tipo_label"] if det else tipo.title(),
        "operacion": det["descripcion"] if det else "—",
        "operacion_id": det["id"] if det else f"{tipo}:{oid}",
        "cliente": cobro["cliente"],
        "cuota": nro, "cuota_label": f"Cuota {nro} de {plazo}",
        "monto": _float(cobro["monto"]), "monto_fmt": moneda(cobro["monto"]),
        "vencimiento": cobro["vencimiento"],
        "estado": cobro["estado"],
        "estado_label": "Pagado" if cobro["estado"] == "PAGADO" else cobro["estado"].title(),
        "medio_pago": cobro["medio_pago"] or "Efectivo",
        "plazo": plazo,
        "cuotas_pagadas": cuotas_pagadas, "cuotas_pagadas_label": f"{cuotas_pagadas} de {plazo}",
        "cuotas_pendientes": cuotas_pend, "cuotas_pendientes_label": f"{cuotas_pend} de {plazo}",
        "total_operacion_fmt": moneda(total_op),
        "total_pagado_fmt": moneda(total_pagado),
        "saldo_pendiente_fmt": moneda(saldo),
        "proxima_cuota": prox_cuota,
        "proximo_vencimiento": prox_venc,
        "detalle": det,
    }
    return render_template("ticket.html", ticket=ticket)

# ─────────────────────────────────────────────────────────
# Catálogo
# ─────────────────────────────────────────────────────────
@app.route("/catalogo")
@login_required
def catalogo():
    marca = request.args.get("marca", "")
    cat   = request.args.get("categoria", "")
    linea = request.args.get("linea", "")
    q     = request.args.get("q", "").strip().lower()
    prods = CATALOGO[:]
    if marca:  prods = [p for p in prods if p["marca"]     == marca]
    if cat:    prods = [p for p in prods if p["categoria"] == cat]
    if linea:  prods = [p for p in prods if p["linea"]     == linea]
    if q:      prods = [p for p in prods if q in p["nombre"].lower() or q in p["descripcion"].lower()]
    return render_template("catalogo.html",
        productos=prods, marcas=MARCAS,
        categorias=CATEGORIAS, lineas=LINEAS,
        marca_filtro=marca, categoria_filtro=cat, linea_filtro=linea,
        busqueda=request.args.get("q", ""), total=len(prods),
        clientes=[dict(c) for c in db.get_clientes()])

# ─────────────────────────────────────────────────────────
# Usuarios
# ─────────────────────────────────────────────────────────
@app.route("/usuarios", methods=["GET", "POST"])
@login_required
@admin_required
def usuarios():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nombre   = request.form.get("nombre", "").strip()
        rol      = request.form.get("rol", "operador")
        if not username or not password:
            flash("Usuario y contraseña son obligatorios.", "danger")
        else:
            try:
                db.crear_usuario(username, generate_password_hash(password), nombre, rol)
                flash(f"Usuario '{username}' creado.", "success")
            except Exception:
                flash("El usuario ya existe.", "danger")
        return redirect(url_for("usuarios"))
    return render_template("usuarios.html", usuarios=db.get_todos_usuarios())

@app.route("/usuarios/eliminar/<int:uid>", methods=["POST"])
@login_required
@admin_required
def eliminar_usuario(uid):
    if uid == session.get("user_id"):
        flash("No podés eliminar tu propio usuario.", "danger")
    else:
        db.eliminar_usuario(uid)
        flash("Usuario eliminado.", "success")
    return redirect(url_for("usuarios"))

if __name__ == "__main__":
    app.run(debug=True)
