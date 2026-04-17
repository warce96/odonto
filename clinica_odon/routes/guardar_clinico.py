from app import app
from flask import request, jsonify
from flask_login import login_required
from models import db, Anamnesis, EventoClinico
import json


@app.route("/guardar_clinico/<int:cliente_id>", methods=["POST"])
@login_required
def guardar_clinico(cliente_id):

    try:
        data = request.get_json()

        # ===== GUARDAR ANAMNESIS =====
        anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()

        if not anamnesis:
            anamnesis = Anamnesis(cliente_id=cliente_id)

        anamnesis.enfermedades = data.get("enfermedades", "")
        anamnesis.alergias = data.get("alergias", "")
        anamnesis.medicamentos = data.get("medicamentos", "")
        anamnesis.observaciones = data.get("observaciones", "")

        db.session.add(anamnesis)

        # ===== EVENTO PARA HISTORIAL (FIX REAL) =====
        evento = EventoClinico(
            cliente_id=cliente_id,
            tipo="anamnesis",  # 🔥 CLAVE (ANTES ESTABA MAL)
            titulo="Actualización de historia clínica",
            descripcion=json.dumps({
                "enfermedades": anamnesis.enfermedades,
                "alergias": anamnesis.alergias,
                "medicamentos": anamnesis.medicamentos,
                "observaciones": anamnesis.observaciones
            })
        )

        db.session.add(evento)
        db.session.commit()

        return jsonify({"status": "ok"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500
