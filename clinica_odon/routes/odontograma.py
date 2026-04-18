from app import app
from flask import request, jsonify
from flask_login import login_required
from models import db, Odontograma, EventoClinico
import json
from datetime import datetime


@app.route("/guardar_odontograma/<int:cliente_id>", methods=["POST"])
@login_required
def guardar_odontograma(cliente_id):

    try:
        data = request.get_json(silent=True) or {}

        # ===== VALIDACIÓN SEGURA =====
        if not isinstance(data, dict) or len(data) == 0:
            return jsonify({
                "status": "error",
                "msg": "No hay dientes seleccionados"
            }), 400

        # ===== GUARDAR ODONTOGRAMA =====
        odontograma = Odontograma.query.filter_by(cliente_id=cliente_id).first()

        if not odontograma:
            odontograma = Odontograma(cliente_id=cliente_id)

        odontograma.dientes = json.dumps(data)

        db.session.add(odontograma)

        # ===== EVENTO PARA HISTORIAL =====
        evento = EventoClinico(
            cliente_id=cliente_id,
            tipo="odontograma",
            titulo="Actualización odontológica",
            descripcion=json.dumps(data),
            fecha=datetime.now()
        )

        db.session.add(evento)

        db.session.commit()

        print("ODONTOGRAMA GUARDADO:", data)

        return jsonify({"status": "ok"})

    except Exception as e:
        print("ERROR GUARDAR ODONTOGRAMA:", e)
        return jsonify({
            "status": "error",
            "msg": str(e)
        }), 500
