from app import app
from flask import request, jsonify
from flask_login import login_required
import json

@app.route("/guardar_odontograma", methods=["POST"])
@login_required
def guardar_odontograma():

    data = request.json
    dientes = data.get("dientes", [])

    # aquí puedes guardar en DB (por ahora simulamos)
    print("Dientes:", dientes)

    return jsonify({"ok": True})