from app import app
from flask import render_template
from flask_login import login_required
from models import Cliente, Ficha, Cuota, Anamnesis, Odontograma, EventoClinico, Pago
from datetime import datetime
import json


def gs(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")


@app.route("/historial/<int:cliente_id>")
@login_required
def historial(cliente_id):

    cliente = Cliente.query.get_or_404(cliente_id)

    fichas = Ficha.query.filter_by(cliente_id=cliente_id).all()

    cuotas = (
        Cuota.query
        .join(Cuota.pago)
        .join(Pago.ficha)
        .filter(Ficha.cliente_id == cliente_id)
        .all()
    )

    anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()
    odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    dientes = {}
    if odontograma and odontograma.dientes:
        try:
            dientes = json.loads(odontograma.dientes)
        except:
            dientes = {}

    eventos = []
    hoy = datetime.now()

    # ================= TRATAMIENTOS =================
    for f in fichas:
        eventos.append({
            "tipo": "tratamiento",
            "titulo": "Tratamiento realizado",
            "descripcion": f"Monto: {gs(f.total)}",
            "fecha": f.fecha
        })

    # ================= CUOTAS =================
    for c in cuotas:

        if c.estado == "PAGADO":
            titulo = "Pago recibido"
        else:
            dias = (c.fecha_vencimiento - hoy.date()).days
            titulo = "Pago vencido" if dias < 0 else "Pago pendiente"

        fecha_ok = datetime(
            c.fecha_vencimiento.year,
            c.fecha_vencimiento.month,
            c.fecha_vencimiento.day
        )

        eventos.append({
            "tipo": "pago",
            "titulo": titulo,
            "descripcion": f"Cuota {c.numero} - {gs(c.monto)}",
            "fecha": fecha_ok
        })

    # ================= EVENTOS CLÍNICOS =================
    eventos_db = EventoClinico.query.filter_by(cliente_id=cliente_id).all()

    for e in eventos_db:
        try:
            detalle = json.loads(e.descripcion)
        except:
            detalle = {}

        eventos.append({
            "tipo": e.tipo,
            "titulo": e.titulo,
            "descripcion": detalle,
            "fecha": e.fecha
        })

    # ================= ORDEN FINAL =================
    eventos.sort(key=lambda x: x["fecha"], reverse=True)

    return render_template(
        "historial.html",
        cliente=cliente,
        eventos=eventos,
        cuotas=cuotas,
        anamnesis=anamnesis,
        dientes=dientes
    )
