from app import app
from flask import render_template
from flask_login import login_required
from models import Ficha, Cuota
from datetime import date
from collections import defaultdict


def gs(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")


@app.route("/")
@login_required
def dashboard():

    fichas = Ficha.query.all()
    cuotas = Cuota.query.all()

    # ================= KPIs =================
    ingresos = sum((f.total or 0) for f in fichas)
    costos = sum((f.costo_total or 0) for f in fichas)
    rentabilidad = ingresos - costos

    hoy = date.today()

    # ================= AGRUPAR =================
    agrupados = defaultdict(list)

    for c in cuotas:

        if not c or c.estado == "PAGADO":
            continue

        if not c.fecha_vencimiento:
            continue

        if not c.pago or not c.pago.ficha:
            continue

        ficha = c.pago.ficha

        # 🔥 VALIDACIÓN CLAVE
        if not ficha.cliente:
            continue

        cliente = ficha.cliente.nombre

        # 🔥 PROTECCIÓN SI NO EXISTE COLUMNA descripcion
        tratamiento = getattr(ficha, "descripcion", None) or "Sin descripción"

        key = (cliente, tratamiento)

        agrupados[key].append(c)

    # ================= PROCESAR =================
    alertas = []

    for (cliente, tratamiento), lista in agrupados.items():

        lista.sort(key=lambda x: x.fecha_vencimiento)

        c = lista[0]

        dias = (c.fecha_vencimiento - hoy).days

        if dias <= 0:
            estado = "VENCIDO"
        elif dias <= 7:
            estado = "PRÓXIMO"
        elif dias <= 30:
            estado = "MES"
        else:
            continue

        alertas.append({
            "cliente": cliente,
            "tratamiento": tratamiento,
            "cuota": f"{c.numero}/{c.pago.cuotas if c.pago else '-'}",
            "estado": estado,
            "monto": gs(c.monto),
            "fecha": c.fecha_vencimiento
        })

    alertas.sort(key=lambda x: x["fecha"])

    return render_template(
        "dashboard.html",
        ingresos=gs(ingresos),
        costos=gs(costos),
        rentabilidad=gs(rentabilidad),
        alertas=alertas
    )
