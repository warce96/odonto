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

    # ✅ SOLO fichas del cliente
    fichas = Ficha.query.filter_by(cliente_id=cliente_id).all()

    # ✅ 🔥 FIX IMPORTANTE → SOLO cuotas del cliente
    cuotas = (
        Cuota.query
        .join(Cuota.pago)
        .join(Pago.ficha)
        .filter(Ficha.cliente_id == cliente_id)
        .all()
    )

    anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()
    odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    # ✅ 🔥 CAMBIO → ahora es dict (para odontograma pro)
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

        # 🔥 FIX FECHA (sin desfase futuro)
        fecha_ok = datetime(
            c.fecha_vencimiento.year,
            c.fecha_vencimiento.month,
            c.fecha_vencimiento.day
        )

        eventos.append({
            "titulo": titulo,
            "descripcion": f"Cuota {c.numero} - {gs(c.monto)}",
            "fecha": fecha_ok
        })

    # ================= EVENTOS CLÍNICOS =================
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

    # ================= ORDEN CORRECTO =================
    eventos = sorted(eventos, key=lambda x: x["fecha"], reverse=True)
    eventos_expandibles = sorted(eventos_expandibles, key=lambda x: x["fecha"], reverse=True)

    return render_template(
        "historial.html",
        cliente=cliente,
        eventos=eventos,
        eventos_expandibles=eventos_expandibles,
        cuotas=cuotas,
        anamnesis=anamnesis,
        dientes=dientes
    )
