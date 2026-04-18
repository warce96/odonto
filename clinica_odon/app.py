from flask import Flask, request
from config import Config
from models import db, Usuario, Odontograma
from flask_login import LoginManager
import json
import os

app = Flask(__name__)
app.config.from_object(Config)

# ================= DB =================
db.init_app(app)

with app.app_context():
    db.create_all()

    # 🔥 CREAR ADMIN AUTOMÁTICO (FLASK 3 COMPATIBLE)
    admin = Usuario.query.filter_by(username="admin").first()

    if not admin:
        user = Usuario(username="admin")
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
        print("✅ Admin creado automáticamente")

# ================= LOGIN =================
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ================= FILTRO MONEDA =================
@app.template_filter('gs')
def guaranies(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")


# ================= ODONTOGRAMA =================
@app.route("/guardar_odontograma/<int:cliente_id>", methods=["POST"])
def guardar_odontograma(cliente_id):

    data = request.json

    odonto = Odontograma.query.filter_by(cliente_id=cliente_id).first()

    if not odonto:
        odonto = Odontograma(cliente_id=cliente_id)

    odonto.dientes = json.dumps(data)

    db.session.add(odonto)
    db.session.commit()

    return {"ok": True}


# ================= RUTAS =================
from routes.auth import *
from routes.dashboard import *
from routes.clientes import *
from routes.fichas import *
from routes.pagos import *
from routes.historial import *
from routes.clinico import *


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
