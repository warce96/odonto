from app import app
from flask import render_template, redirect
from flask_login import login_required
from models import Cuota, db
from datetime import date


# ================= LISTADO =================
@app.route("/pagos")
@login_required
def pagos():

    cuotas = Cuota.query.order_by(Cuota.fecha_vencimiento).all()

    return render_template("pagos.html", cuotas=cuotas, today=date.today())


# ================= CAMBIAR ESTADO =================
@app.route("/cambiar_estado/<int:id>", methods=["POST"])
@login_required
def cambiar_estado(id):

    cuota = Cuota.query.get(id)

    if not cuota:
        return "Error", 404

    # 🔁 TOGGLE
    if cuota.estado == "PAGADO":
        cuota.estado = "PENDIENTE"
    else:
        cuota.estado = "PAGADO"

    db.session.commit()

    return redirect("/pagos")
