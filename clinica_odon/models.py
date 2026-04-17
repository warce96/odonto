from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


# ================= USUARIO =================
class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(200))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ================= CLIENTE =================
class Cliente(db.Model):
    __tablename__ = "cliente"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    ci = db.Column(db.String(20), unique=True)
    telefono = db.Column(db.String(20))

    # Relaciones
    fichas = db.relationship("Ficha", backref="cliente", lazy=True)
    anamnesis = db.relationship("Anamnesis", backref="cliente", uselist=False)
    odontograma = db.relationship("Odontograma", backref="cliente", uselist=False)


# ================= FICHA =================
class Ficha(db.Model):
    __tablename__ = "ficha"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))

    total = db.Column(db.Float)
    costo_total = db.Column(db.Float)

    descripcion = db.Column(db.Text)  # 👈 AGREGAR ESTO

    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    pagos = db.relationship("Pago", backref="ficha", lazy=True)


# ================= PAGO =================
class Pago(db.Model):
    __tablename__ = "pago"

    id = db.Column(db.Integer, primary_key=True)
    ficha_id = db.Column(db.Integer, db.ForeignKey("ficha.id"))
    tipo = db.Column(db.String(20))
    interes = db.Column(db.Float)
    cuotas = db.Column(db.Integer)
    total_final = db.Column(db.Float)

    # Relación correcta (UNICA)
    cuotas_rel = db.relationship("Cuota", backref="pago", lazy=True)


# ================= CUOTA =================
class Cuota(db.Model):
    __tablename__ = "cuota"

    id = db.Column(db.Integer, primary_key=True)
    pago_id = db.Column(db.Integer, db.ForeignKey("pago.id"))
    numero = db.Column(db.Integer)
    monto = db.Column(db.Float)
    fecha_vencimiento = db.Column(db.Date)
    estado = db.Column(db.String(20), default="PENDIENTE")

    # ❌ NO agregar relación aquí (ya viene de Pago)
    # Esto evita errores de join


# ================= ANAMNESIS =================
class Anamnesis(db.Model):
    __tablename__ = "anamnesis"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))

    enfermedades = db.Column(db.Text)
    alergias = db.Column(db.Text)
    medicamentos = db.Column(db.Text)
    observaciones = db.Column(db.Text)

    fecha = db.Column(db.DateTime, default=datetime.utcnow)


# ================= ODONTOGRAMA =================
class Odontograma(db.Model):
    __tablename__ = "odontograma"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))

    dientes = db.Column(db.Text)  # JSON
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


# ================= EVENTO CLÍNICO =================
class EventoClinico(db.Model):
    __tablename__ = "evento_clinico"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))

    tipo = db.Column(db.String(50))  # anamnesis / pago / tratamiento
    titulo = db.Column(db.String(100))
    descripcion = db.Column(db.Text)  # JSON
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
