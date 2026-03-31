from app import app
from flask import render_template, redirect
from flask_login import login_required
from models import Cuota, db
from datetime import date

@app.route("/pagos")
@login_required
def pagos():

    cuotas = Cuota.query.order_by(Cuota.fecha_vencimiento).all()

    # actualizar estado automático
    for c in cuotas:
        if c.estado != "PAGADO":
            if c.fecha_vencimiento < date.today():
                c.estado = "VENCIDO"
            else:
                c.estado = "PENDIENTE"

    db.session.commit()

    return render_template("pagos.html", cuotas=cuotas)


@app.route("/pagar/<int:id>")
@login_required
def pagar(id):

    cuota = Cuota.query.get(id)
    cuota.estado = "PAGADO"
    db.session.commit()

    return redirect("/pagos")