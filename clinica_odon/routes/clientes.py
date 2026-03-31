from app import app
from flask import render_template, request
from flask_login import login_required
from models import Cliente, db

@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    if request.method == "POST":
        cliente = Cliente(
            nombre=request.form["nombre"],
            ci=request.form["ci"],
            telefono=request.form["telefono"]
        )
        db.session.add(cliente)
        db.session.commit()

    return render_template("clientes.html", clientes=Cliente.query.all())