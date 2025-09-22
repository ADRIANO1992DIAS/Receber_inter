import base64
import os
import time
from pathlib import Path
from typing import Iterable, Optional

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


load_dotenv(CREDENTIALS_DIR / ".env")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CONTA_CORRENTE = os.getenv("CONTA_CORRENTE")
CERT_PATH = _resolve_cert_path(os.getenv("CERT_PATH"), "Inter_API_Certificado.crt")
KEY_PATH = _resolve_cert_path(os.getenv("KEY_PATH"), "Inter_API_Chave.key")

AUTH_URL = "https://cdpj.partners.bancointer.com.br/oauth/v2/token"
PDF_URL_TEMPLATE = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/{identificador}/pdf"
MAX_TENTATIVAS = 12
INTERVALO_ESPERA = 5


def obter_token_leitura(
    *,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
) -> str:
    payload = {
        "client_id": client_id or CLIENT_ID,
        "client_secret": client_secret or CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "boleto-cobranca.read",
    }

    response = requests.post(
        AUTH_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        cert=(cert_path or CERT_PATH, key_path or KEY_PATH),
    )
    response.raise_for_status()
    return response.json().get("access_token", "")


def _extrair_bytes_pdf(response: requests.Response) -> Optional[bytes]:
    try:
        data = response.json()
    except ValueError:
        return response.content or None

    if "pdf" in data:
        return base64.b64decode(data["pdf"])
    if "pdfBytes" in data:
        return base64.b64decode(data["pdfBytes"])
    return None


def baixar_pdf_api(
    token: str,
    identificador: str,
    *,
    conta_corrente: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
    aguardar_disponibilidade: bool = True,
) -> Optional[bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": conta_corrente or CONTA_CORRENTE,
    }

    url = PDF_URL_TEMPLATE.format(identificador=identificador)

    tentativas = MAX_TENTATIVAS if aguardar_disponibilidade else 1

    for tentativa in range(1, tentativas + 1):
        print(f"📥 Tentativa {tentativa} - baixando {identificador}")
        response = requests.get(
            url,
            headers=headers,
            cert=(cert_path or CERT_PATH, key_path or KEY_PATH),
        )

        if response.status_code == 200:
            pdf_bytes = _extrair_bytes_pdf(response)
            if pdf_bytes:
                return pdf_bytes
            print("⚠️ Resposta 200 sem conteúdo de PDF.")
            return None

        if response.status_code == 400 and aguardar_disponibilidade:
            print("⏳ PDF não disponível ainda, aguardando...")
            time.sleep(INTERVALO_ESPERA)
            continue

        if response.status_code == 404:
            print("⚠️ Boleto não encontrado para download.")
            return None

        print(f"❌ Erro: {response.status_code}")
        print(response.text)
        return None

    print(f"⚠️ Falha ao baixar PDF do identificador {identificador}")
    return None


def baixar_pdf(
    *,
    nosso_numero: str = "",
    codigo_solicitacao: str = "",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    conta_corrente: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
) -> Optional[bytes]:
    identificador = codigo_solicitacao or nosso_numero
    if not identificador:
        return None
    token = obter_token_leitura(
        client_id=client_id,
        client_secret=client_secret,
        cert_path=cert_path,
        key_path=key_path,
    )
    return baixar_pdf_api(
        token,
        identificador,
        conta_corrente=conta_corrente,
        cert_path=cert_path,
        key_path=key_path,
    )


def salvar_pdf_em_disco(nome_arquivo: str, conteudo: bytes) -> None:
    with open(nome_arquivo, "wb") as stream:
        stream.write(conteudo)
    print(f"✅ Salvo como {nome_arquivo}")


def baixar_todos_pdfs(
    planilha: str = "codigos_emitidos.xlsx",
    coluna_identificador: str = "codigoSolicitacao",
    coluna_nome: str = "nome",
) -> None:
    try:
        df = pd.read_excel(planilha)
    except Exception as exc:  # noqa: BLE001 - manter mensagem direta no CLI
        print("❌ Erro ao abrir planilha:", str(exc))
        return

    token = obter_token_leitura()

    for _, row in df.iterrows():
        identificador = str(row.get(coluna_identificador, "")).strip()
        nome = str(row.get(coluna_nome, "boleto")).strip() or "boleto"
        if not identificador:
            continue
        try:
            pdf_bytes = baixar_pdf_api(token, identificador, conta_corrente=CONTA_CORRENTE)
            if pdf_bytes:
                salvar_pdf_em_disco(nome.replace(" ", "_") + ".pdf", pdf_bytes)
        except Exception as exc:  # noqa: BLE001 - manter fluxo
            print(f"❌ Erro ao baixar boleto de {nome}: {exc}")


if __name__ == "__main__":
    baixar_todos_pdfs()
