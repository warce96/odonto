from app import app
from flask import request, jsonify
from flask_login import login_required
from models import db, Anamnesis, Odontograma, EventoClinico
import json


@app.route("/guardar_clinico/<int:cliente_id>", methods=["POST"])
@login_required
def guardar_clinico(cliente_id):

    try:
        data = request.get_json()

        # ===== ANAMNESIS =====
        anamnesis = Anamnesis.query.filter_by(cliente_id=cliente_id).first()

        if not anamnesis:
            anamnesis = Anamnesis(cliente_id=cliente_id)

        anamnesis.enfermedades = data.get("enfermedades", "")
        anamnesis.alergias = data.get("alergias", "")
        anamnesis.medicamentos = data.get("medicamentos", "")
        anamnesis.observaciones = data.get("observaciones", "")

        db.session.add(anamnesis)

        # ===== ODONTOGRAMA =====
        odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

        if not odontograma:
            odontograma = Odontograma(cliente_id=cliente_id)

        odontograma.dientes = json.dumps(data.get("dientes", []))

        db.session.add(odontograma)

        # ===== EVENTO CLÍNICO =====
        evento = EventoClinico(
            cliente_id=cliente_id,
            tipo="clinico",
            titulo="Actualización clínica",
            descripcion=json.dumps(data)
        )

        db.session.add(evento)

        db.session.commit()

        # ✅ SIEMPRE retornar algo
        return jsonify({"status": "ok"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500