def calcular_total_credito(monto, interes):
    """Calcula el total a cobrar con interes simple sobre el capital."""
    total = float(monto) * (1 + float(interes) / 100)
    return round(total, 2)


def calcular_ganancia_credito(monto, interes):
    """Ganancia estimada del credito: total a cobrar menos capital entregado."""
    ganancia = calcular_total_credito(monto, interes) - float(monto)
    return round(ganancia, 2)


def calcular_cuota(monto, interes, plazo):
    total = calcular_total_credito(monto, interes)
    cuota = total / int(plazo)
    return round(cuota, 2)


def generar_cuotero(monto, interes, plazo, fecha_base=None):
    """Genera un cuotero simple mensual para mostrar antes de otorgar el credito."""
    from datetime import datetime
    from utils.fechas import sumar_meses, hoy

    plazo = int(plazo)
    cuota = calcular_cuota(monto, interes, plazo)
    total = calcular_total_credito(monto, interes)
    saldo = total

    if fecha_base is None:
        fecha_base = hoy()

    cuotas = []
    for nro in range(1, plazo + 1):
        saldo = max(0, round(saldo - cuota, 2))
        cuotas.append({
            "nro": nro,
            "vencimiento": sumar_meses(fecha_base, nro),
            "cuota": cuota,
            "saldo": saldo,
        })
    return cuotas


def calcular_descuento_cheque(monto, porcentaje):
    descuento = float(monto) * float(porcentaje) / 100
    monto_cliente = float(monto) - descuento
    return round(monto_cliente, 2)


def calcular_mora(cuota, dias):
    mora = float(cuota) * 0.02 * int(dias)
    return round(mora, 2)
