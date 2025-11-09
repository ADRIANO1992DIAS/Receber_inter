import re
from pathlib import Path
from typing import Optional

from PyPDF2 import PdfReader


LINHA_DIGITAVEL_RE = re.compile(
    r"(\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14})"
)
CODIGO_BARRAS_RE = re.compile(r"\b(\d{44})\b")


def _apenas_digitos(valor: Optional[str]) -> str:
    return re.sub(r"\D", "", valor or "")


def _linha_digitavel_para_codigo_barras(linha_digitavel: str) -> Optional[str]:
    """Converte a linha digitável (47 dígitos) para o código de barras (44 dígitos)."""
    numeros = _apenas_digitos(linha_digitavel)
    if len(numeros) != 47:
        return None

    bloco_inicial = numeros[0:4]
    dv_geral = numeros[32]
    fator_valor = numeros[33:47]
    campo_livre = numeros[4:9] + numeros[10:20] + numeros[21:31]
    codigo = bloco_inicial + dv_geral + fator_valor + campo_livre
    return codigo if len(codigo) == 44 else None


def _extrair_texto(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    textos = []
    for page in reader.pages:
        try:
            conteudo = page.extract_text()
        except Exception:  # noqa: BLE001
            conteudo = ""
        if conteudo:
            textos.append(conteudo)
    return "\n".join(textos)


def extrair_codigo_barras(pdf_path: Path) -> Optional[str]:
    """Lê o PDF do boleto e tenta identificar o código de barras."""
    if not pdf_path.exists():
        return None

    try:
        texto = _extrair_texto(pdf_path)
    except Exception:  # noqa: BLE001
        return None

    # 1) Busca direta por uma sequência de 44 dígitos
    match = CODIGO_BARRAS_RE.search(texto)
    if match:
        codigo = _apenas_digitos(match.group(1))
        if len(codigo) == 44:
            return codigo

    # 2) Busca pela linha digitável e converte
    match = LINHA_DIGITAVEL_RE.search(texto)
    if match:
        convertido = _linha_digitavel_para_codigo_barras(match.group(1))
        if convertido:
            return convertido

    return None
