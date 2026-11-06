from datetime import datetime, timedelta


def new_state():
    agora = datetime.now()
    usuarios = {
        "admin": {
            "senha": "123",
            "tipo": "admin",
            "veiculos": [
                {"modelo": "Fiat Argo", "placa": "ABC1D23", "vaga": 2, "tipo_veiculo": "carro"},
                {"modelo": "Honda Civic", "placa": "XYZ9K88", "vaga": 4, "tipo_veiculo": "carro"},
            ],
        }
    }
    vagas = [
        {"numero": 1, "status": "livre", "modelo": None, "placa": None, "usuario": None, "entrada": None, "tipo_vaga": "carro"},
        {"numero": 2, "status": "ocupado", "modelo": "Fiat Argo", "placa": "ABC1D23", "usuario": "admin", "entrada": (agora - timedelta(minutes=45)).isoformat(), "tipo_veiculo": "carro", "tipo_vaga": "carro"},
        {"numero": 3, "status": "livre", "modelo": None, "placa": None, "usuario": None, "entrada": None, "tipo_vaga": "carro"},
        {"numero": 4, "status": "ocupado", "modelo": "Honda Civic", "placa": "XYZ9K88", "usuario": "admin", "entrada": (agora - timedelta(minutes=105)).isoformat(), "tipo_veiculo": "carro", "tipo_vaga": "carro"},
        {"numero": 5, "status": "livre", "modelo": None, "placa": None, "usuario": None, "entrada": None, "tipo_vaga": "carro"},
        {"numero": 6, "status": "livre", "modelo": None, "placa": None, "usuario": None, "entrada": None, "tipo_vaga": "carro"},
    ]
    eventos = [
        {
            "tipo": "entrada",
            "vaga": vaga["numero"],
            "usuario": vaga["usuario"],
            "modelo": vaga["modelo"],
            "placa": vaga["placa"],
            "tipo_veiculo": vaga.get("tipo_veiculo", "carro"),
            "horario": vaga["entrada"],
            "valor": 0.0,
        }
        for vaga in vagas
        if vaga["status"] == "ocupado"
    ]
    return {"usuarios": usuarios, "vagas": vagas, "eventos": eventos}


def calcular_tarifa(entrada):
    if not entrada:
        return "0 min", 0.0
    try:
        hora_entrada = datetime.fromisoformat(entrada)
    except (TypeError, ValueError):
        return "0 min", 0.0

    minutos = max(0, int((datetime.now() - hora_entrada).total_seconds() // 60))
    horas, resto = divmod(minutos, 60)
    tempo = f"{horas}h {resto}min" if horas else f"{resto} min"
    valor = 20.0 if minutos <= 60 else 20.0 + (((minutos - 60 + 59) // 60) * 5.0)
    return tempo, valor
