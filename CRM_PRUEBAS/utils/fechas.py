from datetime import datetime
import calendar


def hoy():
    return datetime.now().strftime("%Y-%m-%d")


def sumar_meses(fecha_iso, meses):
    fecha = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
    mes_total = fecha.month - 1 + int(meses)
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia).strftime("%Y-%m-%d")


def fecha_vencimiento(meses=1, desde=None):
    """Calcula la fecha de vencimiento sumando meses desde una fecha base (default: hoy)."""
    base = desde if desde else hoy()
    return sumar_meses(base, meses)
