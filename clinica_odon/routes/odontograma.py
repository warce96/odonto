from app import app
from flask import request, jsonify
from flask_login import login_required
from models import db, Odontograma, EventoClinico
import json


@app.route("/guardar_odontograma/<int:cliente_id>", methods=["POST"])
@login_required
def guardar_odontograma(cliente_id):

    try:
        data = request.get_json()

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
            descripcion=json.dumps(data)
        )

        db.session.add(evento)
        db.session.commit()

        return jsonify({"status": "ok"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500
