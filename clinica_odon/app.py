from flask import Flask
from config import Config
from models import db, Usuario
from flask_login import LoginManager

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@app.template_filter('gs')
def guaranies(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

with app.app_context():
    db.create_all()

def formatear_moneda(valor):
    return "₲ {:,.0f}".format(valor).replace(",", ".")
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
app.jinja_env.filters['gs'] = formatear_moneda

# rutas
from routes.auth import *
from routes.dashboard import *
from routes.clientes import *
from routes.fichas import *
from routes.pagos import *
from routes.historial import *
from routes.clinico import *

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
