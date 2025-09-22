import os
import datetime as dt
from typing import Optional, Dict, Any

try:
    from inter_api import emitir_boletos as _emit_mod
except Exception as exc:  # noqa: BLE001 - guardamos para informar claramente no runtime
    _emit_mod = None  # type: ignore[assignment]
    _emit_import_error = exc
else:
    _emit_import_error = None

try:
    from inter_api import baixar_boletos_pdf as _baixar_mod
except Exception as exc:  # noqa: BLE001 - idem acima
    _baixar_mod = None  # type: ignore[assignment]
    _baixar_import_error = exc
else:
    _baixar_import_error = None


class InterService:
    def __init__(self):
        # Variáveis de ambiente esperadas (.env)
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.conta_corrente = os.getenv("CONTA_CORRENTE")
        self.cert_path = os.getenv("CERT_PATH")
        self.key_path = os.getenv("KEY_PATH")

    def _credenciais_kwargs(self) -> Dict[str, Optional[str]]:
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "conta_corrente": self.conta_corrente,
            "cert_path": self.cert_path,
            "key_path": self.key_path,
        }

    def _assert_emitir_disponivel(self) -> None:
        if _emit_mod is None:
            detalhe = f": {_emit_import_error}" if _emit_import_error else ""
            raise RuntimeError(
                "Módulo inter_api.emitir_boletos indisponível."
                " Verifique dependências e certifique-se de que o arquivo está presente"
                f"{detalhe}."
            )

    def _assert_baixar_disponivel(self) -> None:
        if _baixar_mod is None:
            detalhe = f": {_baixar_import_error}" if _baixar_import_error else ""
            raise RuntimeError(
                "Módulo inter_api.baixar_boletos_pdf indisponível."
                " Verifique dependências e o arquivo correspondente"
                f"{detalhe}."
            )

    def emitir_boleto(self, cliente_dict: Dict[str, Any], data_venc: dt.date) -> Dict[str, Any]:
        """Emite boleto real via API do Banco Inter."""
        self._assert_emitir_disponivel()

        payload = dict(cliente_dict)
        if "valorNominal" not in payload:
            raise ValueError("'valorNominal' é obrigatório para emissão do boleto.")

        try:
            payload["valorNominal"] = float(payload["valorNominal"])
        except Exception as exc:  # noqa: BLE001 - retornamos feedback claro
            raise ValueError(f"Valor nominal inválido: {payload['valorNominal']}") from exc

        for chave in ("cpfCnpj", "nome"):
            if not payload.get(chave):
                raise ValueError(f"'{chave}' é obrigatório para emissão do boleto.")

        return _emit_mod.emitir_boleto(  # type: ignore[union-attr]
            cliente=payload,
            data_vencimento=data_venc,
            **self._credenciais_kwargs(),
        )

    def baixar_pdf(self, identificador: str, *, campo: str = "nosso_numero") -> Optional[bytes]:
        if not identificador:
            return None
        self._assert_baixar_disponivel()

        kwargs = self._credenciais_kwargs()
        if campo == "codigo_solicitacao":
            return _baixar_mod.baixar_pdf(  # type: ignore[union-attr]
                codigo_solicitacao=identificador,
                **kwargs,
            )
        return _baixar_mod.baixar_pdf(  # type: ignore[union-attr]
            nosso_numero=identificador,
            **kwargs,
        )

    def cancelar_boleto(self, nosso_numero: str) -> bool:
        # TODO: Evoluir para chamar a API oficial do Inter para baixa/cancelamento.
        # Por ora, retornamos True apenas para marcar no sistema.
        return True
