from app import app
from flask import render_template
from flask_login import login_required
from models import Cliente, Ficha, Cuota, Anamnesis, Odontograma, Pago, EstadoOdonto
from datetime import datetime
import json


def gs(valor):
    return "₲ {:,.0f}".format(valor or 0).replace(",", ".")


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
            "descripcion": f.descripcion if hasattr(f, "descripcion") and f.descripcion else f"Monto: {gs(f.total)}",
            "fecha": f.fecha or datetime.now()
        })

    # ================= PAGOS =================
    for c in cuotas:

        if c.estado == "PAGADO":
            estado = "PAGADO"
        else:
            if c.fecha_vencimiento:
                dias = (c.fecha_vencimiento - hoy.date()).days
                estado = "VENCIDO" if dias <= 0 else "PENDIENTE"
            else:
                estado = "PENDIENTE"

        eventos.append({
            "tipo": "pago",
            "descripcion": {
                "cuota": c.numero,
                "monto": gs(c.monto)
            },
            "estado": estado,
            "fecha": datetime.combine(c.fecha_vencimiento, datetime.min.time()) if c.fecha_vencimiento else datetime.now()
        })

    # ================= ANAMNESIS =================
    if anamnesis:
        eventos.append({
            "tipo": "anamnesis",
            "titulo": "Historia clínica",
            "descripcion": {
                "enfermedades": anamnesis.enfermedades or "",
                "alergias": anamnesis.alergias or "",
                "medicamentos": anamnesis.medicamentos or "",
                "observaciones": anamnesis.observaciones or ""
            },
            "fecha": anamnesis.fecha or datetime.now()
        })

    # ================= ODONTOGRAMA =================
    dientes = {}

    if odontograma and odontograma.dientes:
        try:
            dientes = json.loads(odontograma.dientes)
        except Exception as e:
            print("ERROR leyendo odontograma:", e)
            dientes = {}

        eventos.append({
            "tipo": "odontograma",
            "titulo": "Odontograma",
            "descripcion": dientes,
            "fecha": odontograma.fecha or datetime.now()
        })

    # ================= ORDEN =================
    eventos.sort(key=lambda x: x.get("fecha") or datetime.now(), reverse=True)

    # ================= ESTADOS DINÁMICOS =================
    estados = EstadoOdonto.query.all()

    # ================= COLORES BASE =================
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
        dientes=dientes,
        colores=colores,
        estados=estados
    )
