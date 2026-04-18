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
            "descripcion": f"Cuota {c.numero} - {gs(c.monto)}",
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
    if odontograma and odontograma.dientes:
        try:
            dientes_json = json.loads(odontograma.dientes)
        except:
            dientes_json = {}

        eventos.append({
            "tipo": "odontograma",
            "titulo": "Odontograma",
            "descripcion": dientes_json,
            "fecha": odontograma.fecha
        })

    # ================= ORDEN =================
    eventos.sort(key=lambda x: x["fecha"], reverse=True)

    colores = {
    "ok": "#22c55e",           # Verde → sano
    "caries": "#ef4444",       # Rojo → caries
    "conducto": "#3b82f6",     # Azul → endodoncia
    "corona": "#a855f7",       # Violeta → corona
    "implante": "#0ea5e9",     # Celeste → implante
    "extraccion": "#111827",   # Negro → extracción
    "ausente": "#9ca3af",      # Gris → diente ausente
    "protesis": "#f59e0b",     # Naranja → prótesis
    "sellado": "#14b8a6",      # Verde agua → sellado
    "fractura": "#b91c1c",     # Rojo oscuro → fractura
    "movilidad": "#eab308",    # Amarillo → movilidad
    "ortodoncia": "#ec4899",   # Rosa → brackets
    "resina": "#6366f1"        # 🔥 Restauración con resina (nuevo)
}

    return render_template(
        "historial.html",
        cliente=cliente,
        eventos=eventos,
        cuotas=cuotas,
        anamnesis=anamnesis,
        dientes={},
        colores=colores
    )
