import os
import re
from pathlib import Path
from typing import Dict, Optional, Any, List

import requests

from django.utils import timezone

from billing.constants import DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE
from billing.models import Boleto, WhatsappConfig

MESSAGE_URL = os.getenv("WHATSAPP_MESSAGE_URL", "http://localhost:3000/send/message")
FILE_URL = os.getenv("WHATSAPP_FILE_URL", "http://localhost:3000/send/file")
DEFAULT_PIX_KEY = os.getenv("WHATSAPP_PIX_KEY", "47.303.364/0001-04")


def _normalize_phone_digits(cliente) -> str:
    raw = f"{cliente.ddd or ''}{cliente.telefone or ''}"
    digits = re.sub(r"\D", "", raw)
    if not digits and cliente.telefone:
        digits = re.sub(r"\D", "", cliente.telefone)
    if not digits:
        return ""

    if digits.startswith("55") and len(digits) in (12, 13):
        return digits

    if len(digits) in (10, 11):
        return f"55{digits}"

    if len(digits) == 9 and cliente.ddd:
        ddd_digits = re.sub(r"\D", "", cliente.ddd)[:3]
        return f"55{ddd_digits}{digits}"

    return ""


def format_whatsapp_phone(cliente) -> Optional[str]:
    digits = _normalize_phone_digits(cliente)
    if not digits:
        return None
    if digits.endswith("@s.whatsapp.net"):
        return digits
    return f"{digits}@s.whatsapp.net"


def _post_json(
    url: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    as_json: bool = True,
) -> Dict[str, Any]:
    try:
        request_kwargs: Dict[str, Any] = {"timeout": 15}
        if files:
            request_kwargs["files"] = files
            request_kwargs["data"] = payload or {}
        elif as_json:
            request_kwargs["json"] = payload or {}
        else:
            request_kwargs["data"] = payload or {}

        response = requests.post(url, **request_kwargs)
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "status_code": None, "payload": None}

    payload: Any
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    ok = response.status_code == 200 and isinstance(payload, dict) and payload.get("code") == "SUCCESS"
    return {
        "ok": ok,
        "status_code": response.status_code,
        "payload": payload,
    }


def send_whatsapp_message(phone: str, message: str) -> Dict[str, Any]:
    return _post_json(
        MESSAGE_URL,
        payload={"phone": phone, "message": message},
        as_json=True,
    )


def send_whatsapp_file(phone: str, file_path: Path) -> Dict[str, Any]:
    with file_path.open("rb") as fp:
        return _post_json(
            FILE_URL,
            payload={"phone": phone},
            files={"file": fp},
            as_json=False,
        )


def _format_valor(valor) -> str:
    try:
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return str(valor)


def dispatch_boleto_via_whatsapp(
    boleto: Boleto,
    *,
    pix_key: Optional[str] = None,
    saudacao_template: Optional[str] = None,
) -> Dict[str, Any]:
    cliente = boleto.cliente
    phone = format_whatsapp_phone(cliente)
    if not phone:
        return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "error": "Telefone inválido ou ausente"}

    if not boleto.pdf:
        return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "error": "Boleto sem PDF anexado"}

    pdf_path = Path(boleto.pdf.path)
    if not pdf_path.exists():
        return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "error": f"Arquivo não encontrado: {pdf_path}"}

    vencimento = boleto.data_vencimento.strftime("%d/%m/%Y") if boleto.data_vencimento else "sem data"
    valor = _format_valor(boleto.valor)
    codigo = boleto.codigo_barras or boleto.linha_digitavel or ""
    pix = pix_key or DEFAULT_PIX_KEY

    steps: List[Dict[str, Any]] = []

    if not saudacao_template:
        try:
            saudacao_template = WhatsappConfig.get_solo().saudacao_template
        except Exception:
            saudacao_template = DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE

    saudacao = _time_based_saudacao()
    template_context = {
        "vencimento": vencimento,
        "valor": valor,
        "cliente": cliente.nome,
        "ven": vencimento,
        "va": valor,
        "saudacao": saudacao,
    }
    try:
        mensagem_inicial = saudacao_template.format(**template_context)
    except KeyError as exc:
        return {
            "boleto_id": boleto.id,
            "cliente": cliente.nome,
            "ok": False,
            "error": f"Variavel ausente no template da mensagem: {exc}",
        }
    for texto in [mensagem_inicial, "Segue a chave pix cnpj", pix]:
        resultado = send_whatsapp_message(phone, texto)
        steps.append({"tipo": "mensagem", "conteudo": texto, **resultado})
        if not resultado.get("ok"):
            return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "phone": phone, "steps": steps}

    arquivo_resultado = send_whatsapp_file(phone, pdf_path)
    steps.append({"tipo": "arquivo", "conteudo": str(pdf_path), **arquivo_resultado})
    if not arquivo_resultado.get("ok"):
        return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "phone": phone, "steps": steps}

    if codigo:
        codigo_resultado = send_whatsapp_message(phone, codigo)
        steps.append({"tipo": "mensagem", "conteudo": codigo, **codigo_resultado})
        if not codigo_resultado.get("ok"):
            return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": False, "phone": phone, "steps": steps}

    return {"boleto_id": boleto.id, "cliente": cliente.nome, "ok": True, "phone": phone, "steps": steps}


def _time_based_saudacao() -> str:
    agora = timezone.localtime()
    hora = agora.hour
    if 0 <= hora < 12:
        return "Bom dia!"
    if 12 <= hora < 18:
        return "Boa tarde!"
    return "Boa noite!"
