from __future__ import annotations

from pathlib import Path
from typing import Set

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Boleto
from .pdf_utils import extrair_codigo_barras

# Evita loop de salvamentos consecutivos
_PROCESSADOS: Set[int] = set()


@receiver(post_save, sender=Boleto)
def preencher_codigo_barras(sender, instance: Boleto, **kwargs):
    if instance.codigo_barras:
        return
    if not instance.pdf:
        return

    try:
        arquivo = Path(instance.pdf.path)
    except Exception:  # noqa: BLE001
        return

    if not arquivo.exists():
        return

    if instance.pk in _PROCESSADOS:
        return

    codigo = extrair_codigo_barras(arquivo)
    if not codigo:
        return

    _PROCESSADOS.add(instance.pk)
    try:
        Boleto.objects.filter(pk=instance.pk).update(codigo_barras=codigo)
    finally:
        _PROCESSADOS.discard(instance.pk)
