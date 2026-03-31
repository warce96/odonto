from app import app
from flask import render_template
from flask_login import login_required
from models import Cliente, Ficha, Cuota, Anamnesis, Odontograma, EventoClinico
from datetime import datetime
import json


def gs(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")


@app.route("/historial/<int:cliente_id>")
@login_required
def historial(cliente_id):

    cliente = Cliente.query.get(cliente_id)

    fichas = Ficha.query.filter_by(cliente_id=cliente_id).all()
    cuotas = Cuota.query.all()

    anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()
    odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    dientes = []
    if odontograma and odontograma.dientes:
        dientes = json.loads(odontograma.dientes)

    eventos = []
    hoy = datetime.today().date()

    # ===== TRATAMIENTOS =====
    for f in fichas:
        eventos.append({
            "titulo": "Tratamiento realizado",
            "descripcion": f"Monto: {gs(f.total)}",
            "fecha": f.fecha
        })

    # ===== CUOTAS =====
    for c in cuotas:

        if c.estado == "PAGADO":
            titulo = "Pago recibido"
        else:
            dias = (c.fecha_vencimiento - hoy).days
            titulo = "Pago vencido" if dias < 0 else "Pago pendiente"

        eventos.append({
            "titulo": titulo,
            "descripcion": f"Cuota {c.numero} - {gs(c.monto)}",
            "fecha": datetime.combine(c.fecha_vencimiento, datetime.min.time())
        })

    # 🔥 NUEVO: EVENTOS CLÍNICOS
    eventos_expandibles = []

    eventos_db = EventoClinico.query.filter_by(cliente_id=cliente_id).all()

    for e in eventos_db:
        try:
            detalle = json.loads(e.descripcion)
        except:
            detalle = {}

        eventos_expandibles.append({
            "titulo": e.titulo,
            "fecha": e.fecha,
            "detalle": detalle
        })

    eventos.sort(key=lambda x: x["fecha"], reverse=True)
    eventos_expandibles.sort(key=lambda x: x["fecha"], reverse=True)

    return render_template(
        "historial.html",
        cliente=cliente,
        eventos=eventos,
        eventos_expandibles=eventos_expandibles,
        cuotas=cuotas,
        anamnesis=anamnesis,
        dientes=dientes
    )




    