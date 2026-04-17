from app import app
from flask import render_template, request, redirect
from flask_login import login_required
from models import Cliente, Ficha, Pago, Cuota, EventoClinico, db
from datetime import date, timedelta
import json


# 🔧 limpiar número tipo 1.250.000
def limpiar_numero(valor):
    if not valor:
        return 0
    return float(valor.replace(".", "").replace(",", "."))


@app.route("/ficha", methods=["GET", "POST"])
@login_required
def ficha():

    if request.method == "POST":

        # ================= DATOS =================
        cliente_id = request.form.get("cliente_id")

        total = limpiar_numero(request.form.get("total"))
        costo = limpiar_numero(request.form.get("costo"))

        descripcion = request.form.get("descripcion")  # 🔥 CLAVE

        # ================= GUARDAR FICHA =================
        ficha = Ficha(
            cliente_id=cliente_id,
            total=total,
            costo_total=costo,
            descripcion=descripcion  # 🔥 NUEVO
        )

        db.session.add(ficha)
        db.session.commit()

        # ================= EVENTO HISTORIAL =================
        evento = EventoClinico(
            cliente_id=cliente_id,
            tipo="tratamiento",
            titulo="Nuevo tratamiento registrado",
            descripcion=json.dumps({
                "total": total,
                "costo": costo,
                "detalle": descripcion
            })
        )

        db.session.add(evento)
        db.session.commit()

        # ================= PAGO =================
        tipo = request.form.get("tipo")

        interes = limpiar_numero(request.form.get("interes"))
        cuotas = int(request.form.get("cuotas") or 1)

        total_final = total * (1 + interes / 100)

        pago = Pago(
            ficha_id=ficha.id,
            tipo=tipo,
            interes=interes,
            cuotas=cuotas,
            total_final=total_final
        )

        db.session.add(pago)
        db.session.commit()

        # ================= CUOTAS =================
        if tipo == "cuotas":

            monto = total_final / cuotas

            fecha_inicio = request.form.get("fecha_inicio")

            if fecha_inicio:
                fecha_base = date.fromisoformat(fecha_inicio)
            else:
                fecha_base = date.today()

            periodo = int(request.form.get("periodo") or 30)

for i in range(cuotas):
    fecha_vencimiento = fecha_base + timedelta(days=periodo * i)

                cuota = Cuota(
                    pago_id=pago.id,
                    numero=i + 1,
                    monto=monto,
                    fecha_vencimiento=fecha_vencimiento,
                    estado="PENDIENTE"
                )

                db.session.add(cuota)

            db.session.commit()

        return redirect("/")

    return render_template("ficha.html", clientes=Cliente.query.all())
