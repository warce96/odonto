from datetime import datetime
from config import LOG_FILE

def log(mensaje):

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    linea = f"[{fecha}] {mensaje}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea)