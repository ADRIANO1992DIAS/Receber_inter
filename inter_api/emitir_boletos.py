import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests
from dotenv import load_dotenv

try:
    import pandas as pd
except Exception:  # noqa: BLE001 - pandas é opcional para rodar via Django
    pd = None  # type: ignore[assignment]

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


# Carregar variáveis de ambiente para uso CLI
load_dotenv(CREDENTIALS_DIR / ".env")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CONTA_CORRENTE = os.getenv("CONTA_CORRENTE")
CERT_PATH = _resolve_cert_path(os.getenv("CERT_PATH"), "Inter_API_Certificado.crt")
KEY_PATH = _resolve_cert_path(os.getenv("KEY_PATH"), "Inter_API_Chave.key")

AUTH_URL = "https://cdpj.partners.bancointer.com.br/oauth/v2/token"
COBRANCA_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas"


def obter_token(
    scope: str = "boleto-cobranca.write",
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
        "scope": scope,
    }

    response = requests.post(
        AUTH_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        cert=(cert_path or CERT_PATH, key_path or KEY_PATH),
    )
    response.raise_for_status()
    return response.json().get("access_token", "")


def _tipo_pessoa(cpf_cnpj: str) -> str:
    digits = "".join(ch for ch in cpf_cnpj or "" if ch.isdigit())
    return "JURIDICA" if len(digits) > 11 else "FISICA"


def _montar_seu_numero(cliente: Dict[str, Any], data_venc: date) -> str:
    fornecido = str(cliente.get("seuNumero", "")).strip()
    if fornecido:
        sanitizado = "".join(ch for ch in fornecido if ch.isalnum()) or fornecido.replace(" ", "")
        return sanitizado[:15]

    cpf_cnpj = "".join(ch for ch in str(cliente.get("cpfCnpj", "")) if ch.isalnum()) or "SN"
    sufixo = data_venc.strftime("%y%m%d")
    max_base = max(0, 15 - len(sufixo))
    base = cpf_cnpj[-max_base:] if max_base else ""
    resultado = (base + sufixo)[:15]
    return resultado or sufixo[-15:]


if pd is not None:
    _pandas_timestamp = (pd.Timestamp,)
else:
    _pandas_timestamp = tuple()


def _normalizar_data(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime.combine(valor, datetime.min.time())
    if _pandas_timestamp and isinstance(valor, _pandas_timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, str):
        valor = valor.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(valor, fmt)
            except ValueError:
                continue
    raise ValueError(f"Data de vencimento inválida: {valor}")


def emitir_boleto_api(
    token: str,
    dados: Dict[str, Any],
    *,
    conta_corrente: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": conta_corrente or CONTA_CORRENTE,
        "Content-Type": "application/json",
    }

    try:
        valor = float(dados["valorNominal"])
    except Exception as exc:  # noqa: BLE001 - queremos retornar erro legível
        raise ValueError(f"Valor inválido: {dados.get('valorNominal')}") from exc

    data_dt = _normalizar_data(dados["dataVencimento"])
    data_formatada = data_dt.strftime("%Y-%m-%d")

    seu_numero = dados.get("seuNumero")
    if not seu_numero:
        numero_base = "".join(ch for ch in str(dados.get("cpfCnpj", "")) if ch.isdigit()) or "SN"
        seu_numero = f"{numero_base}-{data_dt.strftime('%Y%m')}"

    seu_numero = str(seu_numero)[:20]

    body = {
        "seuNumero": seu_numero,
        "valorNominal": valor,
        "dataVencimento": data_formatada,
        "numDiasAgenda": 30,
        "pagador": {
            "cpfCnpj": str(dados.get("cpfCnpj")),
            "tipoPessoa": dados.get("tipoPessoa") or _tipo_pessoa(str(dados.get("cpfCnpj", ""))),
            "nome": str(dados.get("nome")),
            "endereco": str(dados.get("endereco", "")),
            "bairro": str(dados.get("bairro", "")),
            "cidade": str(dados.get("cidade", "")),
            "uf": str(dados.get("uf", "")),
            "cep": str(dados.get("cep", "")),
            "email": str(dados.get("email", "")),
            "ddd": str(dados.get("ddd", "")),
            "telefone": str(dados.get("telefone", "")),
            "numero": str(dados.get("numero", "")),
            "complemento": str(dados.get("complemento", "")),
        },
        "multa": {
            "codigo": dados.get("codigoMulta", "VALORFIXO"),
            "valor": float(dados.get("valorMulta", 1.08)),
        },
        "mora": {
            "codigo": dados.get("codigoMora", "TAXAMENSAL"),
            "taxa": float(dados.get("taxaMora", 5)),
        },
        "mensagem": {
            "linha1": str(dados.get("mensagem1", "Serviços contábeis.")),
            "linha2": str(dados.get("mensagem2", "")),
            "linha3": str(dados.get("mensagem3", "")),
            "linha4": str(dados.get("mensagem4", "")),
            "linha5": str(dados.get("mensagem5", "")),
        },
        "formasRecebimento": dados.get("formasRecebimento", ["BOLETO", "PIX"]),
    }

    response = requests.post(
        COBRANCA_URL,
        headers=headers,
        cert=(cert_path or CERT_PATH, key_path or KEY_PATH),
        json=body,
    )

    if not response.ok:
        print("✅ Body enviado para depuração:")
        print(body)
        print("✅ Resposta do servidor:")
        print(response.text)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:  # noqa: BLE001
        raise RuntimeError("Não foi possível interpretar a resposta da emissão.") from exc


def emitir_boleto(
    *,
    cliente: Dict[str, Any],
    data_vencimento: date,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    conta_corrente: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
) -> Dict[str, Any]:
    token = obter_token(
        client_id=client_id,
        client_secret=client_secret,
        cert_path=cert_path,
        key_path=key_path,
    )

    seu_numero = _montar_seu_numero(cliente, data_vencimento)

    payload: Dict[str, Any] = {
        **cliente,
        "valorNominal": cliente.get("valorNominal"),
        "dataVencimento": data_vencimento,
        "seuNumero": seu_numero,
    }

    resultado = emitir_boleto_api(
        token,
        payload,
        conta_corrente=conta_corrente,
        cert_path=cert_path,
        key_path=key_path,
    )

    return {
        "nossoNumero": resultado.get("nossoNumero", ""),
        "linhaDigitavel": resultado.get("linhaDigitavel", ""),
        "codigoBarras": resultado.get("codigoBarras", ""),
        "txId": resultado.get("txId") or resultado.get("codigoSolicitacao", ""),
        "codigoSolicitacao": resultado.get("codigoSolicitacao", ""),
        "pdfBytes": resultado.get("pdfBytes"),
    }


def salvar_codigos_excel(lista_codigos: Iterable[Iterable[Any]]) -> None:
    if pd is None:
        raise RuntimeError("pandas não está disponível para salvar os códigos em Excel.")
    df = pd.DataFrame(list(lista_codigos), columns=["codigoSolicitacao", "nome"])
    df.to_excel("codigos_emitidos.xlsx", index=False)
    print("📄 Todos os códigos salvos em 'codigos_emitidos.xlsx'")


if __name__ == "__main__":
    try:
        if pd is None:
            raise RuntimeError(
                "pandas não está instalado. Instale-o para executar a emissão via linha de comando."
            )
        token = obter_token()
        df = pd.read_excel(
            "clientes_boletos_092025_teste.xlsx",
            dtype=str,
            sheet_name="BOLETOS",
        )

        codigos_emitidos = []

        for _, row in df.iterrows():
            try:
                retorno = emitir_boleto_api(
                    token,
                    row.to_dict(),
                    conta_corrente=CONTA_CORRENTE,
                )
                nome_cliente = str(row.get("nome", "cliente")).strip().replace(" ", "_")
                codigos_emitidos.append([retorno.get("codigoSolicitacao"), nome_cliente])
            except Exception as exc:  # noqa: BLE001 - logs completos no console
                print(f"❌ Erro ao emitir boleto para {row.get('nome')}: {exc}")

        if codigos_emitidos:
            salvar_codigos_excel(codigos_emitidos)

    except Exception as exc:  # noqa: BLE001 - execução CLI precisa do erro
        print("❌ Erro geral:", str(exc))
