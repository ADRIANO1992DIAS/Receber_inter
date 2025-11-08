import base64
import os
import unicodedata
import datetime as dt
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
CREDENTIALS_DIR = BASE_DIR / "config" / "inter"
ENV_PATH = CREDENTIALS_DIR / ".env"

load_dotenv(ENV_PATH)

AUTH_URL = "https://cdpj.partners.bancointer.com.br/oauth/v2/token"
COBRANCA_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas"
COBRANCA_CANCELAR_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/{codigo_solicitacao}/cancelar"
CANCELAR_BOLETO_V2_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v2/boletos/{nosso_numero}/cancelar"
PDF_URL_TEMPLATE = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/{identificador}/pdf"
DETALHE_COBRANCA_URL = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/{identificador}"


def _tipo_pessoa(cpf_cnpj: str) -> str:
    digitos = "".join(ch for ch in cpf_cnpj if ch.isdigit())
    return "JURIDICA" if len(digitos) > 11 else "FISICA"


def _resolve_cert_path(raw_value: Optional[str], filename: str) -> str:
    if raw_value:
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = CREDENTIALS_DIR / candidate
    else:
        candidate = CREDENTIALS_DIR / filename
    return str(candidate)


def _montar_seu_numero(cliente_dict: Dict[str, Any], data_venc: dt.date) -> str:
    fornecido = str(cliente_dict.get("seuNumero", "")).strip()
    if fornecido:
        sanitizado = "".join(ch for ch in fornecido if ch.isalnum()) or fornecido.replace(" ", "")
        return sanitizado[:15]

    cpf_cnpj = "".join(ch for ch in str(cliente_dict.get("cpfCnpj", "")) if ch.isalnum()) or "SN"
    sufixo = data_venc.strftime("%y%m%d")  # garante diferença por competência/dia
    max_base = max(0, 15 - len(sufixo))
    base = cpf_cnpj[-max_base:] if max_base else ""
    resultado = (base + sufixo)[:15]
    return resultado or sufixo[-15:]


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit]


class InterService:
    def __init__(self) -> None:
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.conta_corrente = os.getenv("CONTA_CORRENTE")
        self.cert_path = _resolve_cert_path(os.getenv("CERT_PATH"), "Inter_API_Certificado.crt")
        self.key_path = _resolve_cert_path(os.getenv("KEY_PATH"), "Inter_API_Chave.key")
        self._token_cache: Dict[str, Dict[str, Any]] = {}

        if not all([self.client_id, self.client_secret, self.conta_corrente]):
            raise RuntimeError("CLIENT_ID, CLIENT_SECRET e CONTA_CORRENTE precisam estar definidos no .env.")

    def _obter_token(self, scope: str) -> str:
        agora = dt.datetime.utcnow()
        cache = self._token_cache.get(scope)
        if cache:
            expires_at = cache.get("expires_at")
            token = cache.get("token")
            if token and isinstance(expires_at, dt.datetime) and expires_at > agora:
                return token

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": scope,
        }

        response = requests.post(
            AUTH_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            cert=(self.cert_path, self.key_path),
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Nao foi possivel obter token de acesso do Banco Inter.")
        try:
            expires_in = int(data.get("expires_in", 600))
        except (TypeError, ValueError):
            expires_in = 600
        margem = 60 if expires_in > 120 else int(expires_in * 0.2)
        expires_at = agora + dt.timedelta(seconds=max(30, expires_in - margem))
        self._token_cache[scope] = {"token": token, "expires_at": expires_at}
        return token

    def _formatar_pagador(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        cpf_cnpj = str(dados.get("cpfCnpj", ""))
        ddd = "".join(ch for ch in str(dados.get("ddd", "")) if ch.isdigit())[:3]
        telefone = "".join(ch for ch in str(dados.get("telefone", "")) if ch.isdigit())
        if len(telefone) > 9:
            telefone = telefone[-9:]
        return {
            "cpfCnpj": cpf_cnpj,
            "tipoPessoa": _tipo_pessoa(cpf_cnpj),
            "nome": str(dados.get("nome", "")),
            "endereco": str(dados.get("endereco", "")),
            "bairro": str(dados.get("bairro", "")),
            "cidade": str(dados.get("cidade", "")),
            "uf": str(dados.get("uf", "")),
            "cep": str(dados.get("cep", "")),
            "email": str(dados.get("email", "")),
            "ddd": ddd,
            "telefone": telefone,
            "numero": str(dados.get("numero", "")),
            "complemento": _truncate_text(dados.get("complemento", ""), 30),
        }

    def emitir_boleto(self, cliente_dict: Dict[str, Any], data_venc: dt.date) -> Dict[str, Any]:
        if "valorNominal" not in cliente_dict:
            raise ValueError("O cliente precisa possuir o campo 'valorNominal'.")

        try:
            valor_nominal = float(cliente_dict["valorNominal"])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Valor nominal inválido: {cliente_dict['valorNominal']}") from exc

        cpf_cnpj = str(cliente_dict.get("cpfCnpj", "")).strip()
        if not cpf_cnpj:
            raise ValueError("CPF/CNPJ é obrigatório para emissão do boleto.")

        nome = str(cliente_dict.get("nome", "")).strip()
        if not nome:
            raise ValueError("Nome é obrigatório para emissão do boleto.")

        seu_numero = _montar_seu_numero(cliente_dict, data_venc)

        token = self._obter_token("boleto-cobranca.write")

        body = {
            "seuNumero": seu_numero,
            "valorNominal": valor_nominal,
            "dataVencimento": data_venc.strftime("%Y-%m-%d"),
            "numDiasAgenda": 30,
            "pagador": self._formatar_pagador(cliente_dict),
            "multa": {
                "codigo": cliente_dict.get("codigoMulta", "VALORFIXO"),
                "valor": float(cliente_dict.get("valorMulta", 1.08)),
            },
            "mora": {
                "codigo": cliente_dict.get("codigoMora", "TAXAMENSAL"),
                "taxa": float(cliente_dict.get("taxaMora", 5)),
            },
            "mensagem": {
                "linha1": str(cliente_dict.get("mensagem1", "Serviços contábeis.")),
                "linha2": str(cliente_dict.get("mensagem2", "")),
                "linha3": str(cliente_dict.get("mensagem3", "")),
                "linha4": str(cliente_dict.get("mensagem4", "")),
                "linha5": str(cliente_dict.get("mensagem5", "")),
            },
            "formasRecebimento": cliente_dict.get("formasRecebimento", ["BOLETO", "PIX"]),
        }

        response = requests.post(
            COBRANCA_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "x-conta-corrente": self.conta_corrente,
                "Content-Type": "application/json",
            },
            cert=(self.cert_path, self.key_path),
            json=body,
        )

        if not response.ok:
            conteudo = response.text
            raise RuntimeError(
                f"Falha ao emitir boleto para {nome}. Status {response.status_code}. Resposta: {conteudo}"
            )

        try:
            retorno = response.json()
        except ValueError as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Falha ao interpretar resposta da emissão para {nome}."
            ) from exc

        return {
            "nossoNumero": retorno.get("nossoNumero", ""),
            "linhaDigitavel": retorno.get("linhaDigitavel", ""),
            "codigoBarras": retorno.get("codigoBarras", ""),
            "txId": retorno.get("txId") or retorno.get("codigoSolicitacao", ""),
            "codigoSolicitacao": retorno.get("codigoSolicitacao", ""),
            "pdfBytes": retorno.get("pdfBytes"),
        }

    def baixar_pdf(self, identificador: str, *, campo: str = "nosso_numero") -> Optional[bytes]:
        if not identificador:
            return None

        token = self._obter_token("boleto-cobranca.read")
        url = PDF_URL_TEMPLATE.format(identificador=identificador)

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "x-conta-corrente": self.conta_corrente,
            },
            cert=(self.cert_path, self.key_path),
        )

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return response.content or None
            if "pdf" in data:
                return base64.b64decode(data["pdf"]) if data["pdf"] else None
            if "pdfBytes" in data:
                return base64.b64decode(data["pdfBytes"]) if data["pdfBytes"] else None
            return response.content or None

        if response.status_code == 404:
            return None

        raise RuntimeError(
            f"Falha ao baixar PDF ({response.status_code}): {response.text}"
        )

    def recuperar_cobranca_detalhada(self, identificador: str, *, campo: str = "nosso_numero") -> Optional[Dict[str, Any]]:
        if not identificador:
            return None

        token = self._obter_token("boleto-cobranca.read")
        url = DETALHE_COBRANCA_URL.format(identificador=identificador)
        tipo_map = {
            "nosso_numero": "NOSSONUMERO",
            "codigo_solicitacao": "CODIGOSOLICITACAO",
            "tx_id": "TXID",
        }
        params = {}
        tipo = tipo_map.get(campo)
        if tipo:
            params["tipo"] = tipo

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "x-conta-corrente": self.conta_corrente,
            },
            params=params,
            cert=(self.cert_path, self.key_path),
        )

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None

        if response.status_code == 404:
            return None

        raise RuntimeError(
            f"Falha ao recuperar cobranca ({response.status_code}): {response.text}"
        )

    def cancelar_boleto(
        self,
        *,
        codigo_solicitacao: str = "",
        nosso_numero: str = "",
        motivo: str = "Solicitação do cliente",
    ) -> Dict[str, Any]:
        if not codigo_solicitacao and not nosso_numero:
            raise ValueError("Informe codigo_solicitacao ou nosso_numero para cancelar o boleto.")

        motivo = (motivo or "Solicitação do cliente").strip() or "Solicitação do cliente"
        motivo_v3 = motivo[:50]

        token = self._obter_token("boleto-cobranca.write")
        headers = {
            "Authorization": f"Bearer {token}",
            "x-conta-corrente": self.conta_corrente,
            "Content-Type": "application/json",
        }

        erros: List[str] = []

        if codigo_solicitacao:
            url = COBRANCA_CANCELAR_URL.format(codigo_solicitacao=codigo_solicitacao)
            response = requests.post(
                url,
                headers=headers,
                cert=(self.cert_path, self.key_path),
                json={"motivoCancelamento": motivo_v3},
            )
            if response.ok:
                payload: Dict[str, Any]
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                payload.setdefault("codigoSolicitacao", codigo_solicitacao)
                payload.setdefault("motivoCancelamento", motivo_v3)
                payload.setdefault("via", "v3")
                payload.setdefault("status_code", response.status_code)
                return payload
            erros.append(
                f"codigoSolicitacao {codigo_solicitacao}: {response.status_code} - {response.text}"
            )

        if nosso_numero:
            url = CANCELAR_BOLETO_V2_URL.format(nosso_numero=nosso_numero)
            motivo_enum = self._normalizar_motivo_v2(motivo)
            response = requests.post(
                url,
                headers=headers,
                cert=(self.cert_path, self.key_path),
                json={"motivoCancelamento": motivo_enum},
            )
            if response.ok:
                payload: Dict[str, Any]
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                payload.setdefault("nossoNumero", nosso_numero)
                payload.setdefault("motivoCancelamento", motivo_enum)
                payload.setdefault("via", "v2")
                payload.setdefault("status_code", response.status_code)
                return payload
            erros.append(
                f"nossoNumero {nosso_numero}: {response.status_code} - {response.text}"
            )

        raise RuntimeError("; ".join(erros))

    @staticmethod
    def _normalizar_motivo_v2(motivo: str) -> str:
        padrao = "Solicitação do cliente"
        if not motivo:
            motivo = padrao
        texto = (
            unicodedata.normalize("NFKD", motivo.strip())
            .encode("ASCII", "ignore")
            .decode()
            .upper()
        )
        texto_sem_espaco = "".join(ch for ch in texto if ch.isalpha())
        opcoes = {"ACERTOS", "APEDIDODOCLIENTE", "PAGODIRETOAOCLIENTE", "SUBSTITUICAO"}
        if texto_sem_espaco in opcoes:
            return texto_sem_espaco
        return "APEDIDODOCLIENTE"
