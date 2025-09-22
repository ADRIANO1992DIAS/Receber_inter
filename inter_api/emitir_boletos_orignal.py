import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CONTA_CORRENTE = os.getenv("CONTA_CORRENTE")
CERT_PATH = "Inter_API_Certificado.crt"
KEY_PATH = "Inter_API_Chave.key"

AUTH_URL = "https://cdpj.partners.bancointer.com.br/oauth/v2/token"
COBRANCA_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas"


def obter_token():
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "boleto-cobranca.write"
    }

    response = requests.post(
        AUTH_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        cert=(CERT_PATH, KEY_PATH)
    )
    response.raise_for_status()
    return response.json().get("access_token")


def emitir_boleto(token, dados):
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": CONTA_CORRENTE,
        "Content-Type": "application/json"
    }

    # Tratamento do valor nominal
    try:
        valor = float(dados["valorNominal"])
    except:
        raise ValueError(f"Valor inválido: {dados['valorNominal']}")

    # Tratamento da data de vencimento
    data_original = str(dados["dataVencimento"]).strip()
    try:
        if isinstance(dados["dataVencimento"], pd.Timestamp):
            data_obj = dados["dataVencimento"].to_pydatetime()
        else:
            try:
                # Tenta formato do Excel convertido em string
                data_obj = datetime.strptime(data_original, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # Tenta formato ano-mês-dia sem hora
                    data_obj = datetime.strptime(data_original, "%Y-%m-%d")
                except ValueError:
                    # Tenta formato dia-mês-ano
                    data_obj = datetime.strptime(data_original, "%d-%m-%Y")
    except Exception as e:
        raise ValueError(f"Data de vencimento inválida: {data_original} ({e})")

    data_formatada = data_obj.strftime("%Y-%m-%d")

    # Monta body para a API do Banco Inter
    body = {
        "seuNumero": str(dados["seuNumero"]),
        "valorNominal": valor,
        "dataVencimento": str(data_formatada),
        "numDiasAgenda": 30,
        "pagador": {
            "cpfCnpj": str(dados["cpfCnpj"]),
            "tipoPessoa": "JURIDICA",
            "nome": str(dados["nome"]),
            "endereco": str(dados["endereco"]),
            "bairro": str(dados["bairro"]),
            "cidade": str(dados["cidade"]),
            "uf": str(dados["uf"]),
            "cep": str(dados["cep"]),
            "email": str(dados["email"]),
            "ddd": str(dados["ddd"]),
            "telefone": str(dados["telefone"]),
            "numero": str(dados["numero"]),
            "complemento": str(dados["complemento"])
        },
        "multa": {
            "codigo": "VALORFIXO",
            "valor": 1.08  # valor fixo em reais
        },
        "mora": {
            "codigo": "TAXAMENSAL",
            "taxa": 5
        },
        "mensagem": {
            "linha1": "Serviços contábeis.",
            "linha2": "",
            "linha3": "",
            "linha4": "",
            "linha5": ""
        },
        "formasRecebimento": ["BOLETO", "PIX"]
    }

    response = requests.post(
        COBRANCA_URL,
        headers=headers,
        cert=(CERT_PATH, KEY_PATH),
        json=body
    )

    if response.status_code != 201:
        print("✅ Body enviado para depuração:")
        print(body)
        print("✅ Resposta do servidor:")
        print(response.text)

    response.raise_for_status()
    retorno = response.json()
    codigo = retorno.get("codigoSolicitacao")
    print(f"✅ Cobrança emitida para {dados['nome']}: {codigo}")
    return codigo