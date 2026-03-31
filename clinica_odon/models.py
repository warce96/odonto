from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(200))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    ci = db.Column(db.String(20), unique=True)
    telefono = db.Column(db.String(20))


class Ficha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer)
    total = db.Column(db.Float)
    costo_total = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ficha_id = db.Column(db.Integer)
    tipo = db.Column(db.String(20))
    interes = db.Column(db.Float)
    cuotas = db.Column(db.Integer)
    total_final = db.Column(db.Float)


class Cuota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pago_id = db.Column(db.Integer)
    numero = db.Column(db.Integer)
    monto = db.Column(db.Float)
    fecha_vencimiento = db.Column(db.Date)
    estado = db.Column(db.String(20), default="PENDIENTE")


# 🔥 NUEVO
class Anamnesis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer)
    enfermedades = db.Column(db.Text)
    alergias = db.Column(db.Text)
    medicamentos = db.Column(db.Text)
    observaciones = db.Column(db.Text)


class Odontograma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer)
    dientes = db.Column(db.Text)  # JSON


# 🔥 CLAVE
class EventoClinico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer)
    tipo = db.Column(db.String(50))
    titulo = db.Column(db.String(100))  # 🔥 IMPORTANTE
    descripcion = db.Column(db.Text)    # JSON
    fecha = db.Column(db.DateTime, default=datetime.utcnow)