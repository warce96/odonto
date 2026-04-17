from app import app
from flask import render_template
from flask_login import login_required
from models import Ficha, Cuota, Cliente, Pago
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

        if c.estado == "PAGADO":
            continue

        if not c.fecha_vencimiento:
            continue

        # relaciones directas (más limpio)
        if not c.pago or not c.pago.ficha:
            continue

        cliente = c.pago.ficha.cliente
        tratamiento = c.pago.ficha.descripcion or "Sin descripción"

        key = (cliente.nombre, tratamiento)

        agrupados[key].append(c)

    # ================= PROCESAR =================
    alertas = []

    for (cliente, tratamiento), lista in agrupados.items():

        # ordenar por fecha
        lista.sort(key=lambda x: x.fecha_vencimiento)

        c = lista[0]  # 🔥 SOLO LA PRÓXIMA CUOTA

        dias = (c.fecha_vencimiento - hoy).days

        # 🔥 lógica correcta
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
            "cuota": f"{c.numero}/{c.pago.cuotas}",
            "estado": estado,
            "monto": gs(c.monto),
            "fecha": c.fecha_vencimiento
        })

    # ordenar final
    alertas.sort(key=lambda x: x["fecha"])

    return render_template(
        "dashboard.html",
        ingresos=gs(ingresos),
        costos=gs(costos),
        rentabilidad=gs(rentabilidad),
        alertas=alertas
    )
