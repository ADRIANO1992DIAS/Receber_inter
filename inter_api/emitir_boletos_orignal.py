import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
CREDENTIALS_DIR = BASE_DIR / "config" / "inter"


def _resolve_cert_path(raw_value: Optional[str], filename: str) -> str:
    if raw_value:
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = CREDENTIALS_DIR / candidate
    else:
        candidate = CREDENTIALS_DIR / filename
    return str(candidate)


# Mantém compatibilidade com scripts antigos, mas respeitando limite da API
def _montar_seu_numero(dados: Dict[str, str], data_vencimento: datetime) -> str:
    fornecido = str(dados.get("seuNumero", "")).strip()
    if fornecido:
        sanitizado = "".join(ch for ch in fornecido if ch.isalnum()) or fornecido.replace(" ", "")
        return sanitizado[:15]

    cpf_cnpj = "".join(ch for ch in str(dados.get("cpfCnpj", "")) if ch.isalnum()) or "SN"
    sufixo = data_vencimento.strftime("%y%m%d")
    max_base = max(0, 15 - len(sufixo))
    base = cpf_cnpj[-max_base:] if max_base else ""
    resultado = (base + sufixo)[:15]
    return resultado or sufixo[-15:]


# Carregar variáveis de ambiente
load_dotenv(CREDENTIALS_DIR / ".env")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CONTA_CORRENTE = os.getenv("CONTA_CORRENTE")
CERT_PATH = _resolve_cert_path(os.getenv("CERT_PATH"), "Inter_API_Certificado.crt")
KEY_PATH = _resolve_cert_path(os.getenv("KEY_PATH"), "Inter_API_Chave.key")

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
        "seuNumero": _montar_seu_numero(dados, data_obj),
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

    if not response.ok:
        print("✅ Body enviado para depuração:")
        print(body)
        print("✅ Resposta do servidor:")
        print(response.text)

    response.raise_for_status()
    try:
        retorno = response.json()
    except ValueError as exc:
        raise RuntimeError("Não foi possível interpretar a resposta da emissão.") from exc
    codigo = retorno.get("codigoSolicitacao")
    print(f"✅ Cobrança emitida para {dados['nome']}: {codigo}")
    return codigo
