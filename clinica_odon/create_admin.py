from app import app
from models import db, Usuario

with app.app_context():
    if not Usuario.query.filter_by(username="admin").first():
        user = Usuario(username="admin")
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
        print("Usuario admin creado")
    else:
        print("Ya existe admin")