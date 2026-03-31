from app import app
from flask import render_template, request, redirect
from flask_login import login_user, logout_user
from models import Usuario

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Usuario.query.filter_by(username=request.form["username"]).first()

        if user and user.check_password(request.form["password"]):
            login_user(user)
            return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    return redirect("/login")