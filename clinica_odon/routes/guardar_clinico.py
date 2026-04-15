descripcion=json.dumps({
    "tipo": "anamnesis",
    "enfermedades": data.get("enfermedades"),
    "alergias": data.get("alergias"),
    "medicamentos": data.get("medicamentos"),
    "observaciones": data.get("observaciones")
})
