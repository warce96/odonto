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

    # ===== DATOS BASE =====
    fichas = Ficha.query.filter_by(cliente_id=cliente_id).all()

    # 🔥 IMPORTANTE: cuotas globales (para pestaña pagos)
    cuotas = (
        Cuota.query
        .join(Pago, Cuota.pago_id == Pago.id)
        .join(Ficha, Pago.ficha_id == Ficha.id)
        .filter(Ficha.cliente_id == cliente_id)
        .order_by(Cuota.numero)
        .all()
    )

    anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()
    odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    # ===== ODONTOGRAMA =====
    dientes = {}
    if odontograma and odontograma.dientes:
        try:
            dientes = json.loads(odontograma.dientes)
        except:
            dientes = {}

    eventos = []
    hoy = datetime.now()

    # ================= TRATAMIENTOS + CUOTAS =================
    for f in fichas:

        cuotas_ficha = (
            Cuota.query
            .join(Pago, Cuota.pago_id == Pago.id)
            .filter(Pago.ficha_id == f.id)
            .order_by(Cuota.numero)
            .all()
        )

        cuotas_detalle = []
        total_pagado = 0

        for c in cuotas_ficha:

            if c.estado == "PAGADO":
                estado = "PAGADO"
                total_pagado += c.monto
            else:
                dias = (c.fecha_vencimiento - hoy.date()).days
                estado = "VENCIDO" if dias < 0 else "PENDIENTE"

            cuotas_detalle.append({
                "numero": c.numero,
                "monto": gs(c.monto),
                "estado": estado,
                "fecha": c.fecha_vencimiento.strftime("%Y-%m-%d")
            })

        # 🔥 ESTADO DEL TRATAMIENTO
        total = f.total or 0

        if total_pagado >= total:
            estado_trat = "PAGADO"
        elif total_pagado == 0:
            estado_trat = "PENDIENTE"
        else:
            estado_trat = "PARCIAL"

        eventos.append({
            "tipo": "tratamiento",
            "titulo": "Tratamiento realizado",
            "descripcion": f"Monto: {gs(total)}",
            "fecha": f.fecha,
            "estado": estado_trat,
            "cuotas": cuotas_detalle
        })

    # ================= EVENTOS DE PAGOS (timeline) =================
    for c in cuotas:

        if c.estado == "PAGADO":
            titulo = "Pago recibido"
        else:
            dias = (c.fecha_vencimiento - hoy.date()).days
            titulo = "Pago vencido" if dias < 0 else "Pago pendiente"

        eventos.append({
            "tipo": "pago",
            "titulo": titulo,
            "descripcion": f"Cuota {c.numero} - {gs(c.monto)}",
            "fecha": datetime.combine(c.fecha_vencimiento, datetime.min.time())
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
        cuotas=cuotas,   # 🔥 CLAVE PARA TAB PAGOS
        anamnesis=anamnesis,
        dientes=dientes
    )
