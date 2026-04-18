from app import app
from flask import render_template
from flask_login import login_required
from models import Cliente, Ficha, Cuota, Anamnesis, Odontograma, Pago
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
        .join(Pago, Cuota.pago_id == Pago.id)
        .join(Ficha, Pago.ficha_id == Ficha.id)
        .filter(Ficha.cliente_id == cliente_id)
        .order_by(Cuota.numero)
        .all()
    )

    anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()
    odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    eventos = []
    hoy = datetime.now()

    # ================= TRATAMIENTOS =================
    for f in fichas:
        eventos.append({
            "tipo": "tratamiento",
            "titulo": "Tratamiento",
            "descripcion": getattr(f, "descripcion", f"Monto: {gs(f.total)}"),
            "fecha": f.fecha
        })

    # ================= PAGOS =================
    for c in cuotas:

        if c.estado == "PAGADO":
            estado = "PAGADO"
        else:
            dias = (c.fecha_vencimiento - hoy.date()).days
            estado = "VENCIDO" if dias < 0 else "PENDIENTE"

        eventos.append({
            "tipo": "pago",
            "descripcion": {
                "cuota": c.numero,
                "monto": gs(c.monto)
            },
            "estado": estado,
            "fecha": datetime.combine(c.fecha_vencimiento, datetime.min.time())
        })

    # ================= ANAMNESIS =================
    if anamnesis:
        eventos.append({
            "tipo": "anamnesis",
            "titulo": "Historia clínica",
            "descripcion": {
                "enfermedades": anamnesis.enfermedades,
                "alergias": anamnesis.alergias,
                "medicamentos": anamnesis.medicamentos,
                "observaciones": anamnesis.observaciones
            },
            "fecha": anamnesis.fecha
        })

    # ================= ODONTOGRAMA =================
    dientes = {}

    if odontograma and odontograma.dientes:
        try:
            dientes = json.loads(odontograma.dientes)
        except:
            dientes = {}

        eventos.append({
            "tipo": "odontograma",
            "titulo": "Odontograma",
            "descripcion": dientes,
            "fecha": odontograma.fecha
        })

    # ================= ORDEN =================
    eventos.sort(key=lambda x: x["fecha"], reverse=True)

    # 🎨 COLORES (podés expandir o hacer dinámico después)
    colores = {
        "ok": "#22c55e",
        "caries": "#ef4444",
        "conducto": "#3b82f6",
        "corona": "#a855f7",
        "implante": "#0ea5e9",
        "extraccion": "#991b1b",
        "ausente": "#374151"
    }

    return render_template(
        "historial.html",
        cliente=cliente,
        eventos=eventos,
        cuotas=cuotas,
        anamnesis=anamnesis,
        dientes=dientes,   # 🔥 FIX CLAVE
        colores=colores
    )
