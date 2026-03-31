from app import app
from flask import render_template
from flask_login import login_required
from models import Ficha, Cuota, Cliente, Pago
from datetime import date


def gs(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")


@app.route("/")
@login_required
def dashboard():

    fichas = Ficha.query.all()
    cuotas = Cuota.query.all()

    ingresos = sum((f.total or 0) for f in fichas)
    costos = sum((f.costo_total or 0) for f in fichas)
    rentabilidad = ingresos - costos

    hoy = date.today()
    alertas = []

    for c in cuotas:

        if c.estado == "PAGADO":
            continue

        if not c.fecha_vencimiento:
            continue

        dias = (c.fecha_vencimiento - hoy).days

        if dias < 0:
            estado = "VENCIDO"
        elif dias == 0:
            estado = "HOY"
        elif dias <= 7:
            estado = "SEMANA"
        elif dias <= 30:
            estado = "MES"
        else:
            continue

        # 🔥 obtener cliente real
        pago = Pago.query.get(c.pago_id)
        ficha = Ficha.query.get(pago.ficha_id) if pago else None
        cliente = Cliente.query.get(ficha.cliente_id) if ficha else None

        alertas.append({
            "cliente": cliente.nombre if cliente else "Sin cliente",
            "cuota": c.numero,
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