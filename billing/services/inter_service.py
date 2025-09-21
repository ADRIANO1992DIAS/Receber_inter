
import os
import datetime as dt
from typing import Optional, Dict, Any

# Este módulo foi feito para PLUGAR seus scripts existentes:
# - inter_api/emitir_boletos.py
# - inter_api/baixar_boletos_pdf.py
#
# Se estiverem presentes, usaremos suas funções. Caso contrário,
# operamos em modo 'simulado' (sem integração real).
#
# Para cancelar boleto: deixamos um hook pronto (cancel_boleto) para evoluir.

def _import_optional(path_module: str):
    try:
        return __import__(path_module, fromlist=['*'])
    except Exception:
        return None

_emit_mod = _import_optional("inter_api.emitir_boletos")
_baixar_mod = _import_optional("inter_api.baixar_boletos_pdf")

class InterService:
    def __init__(self):
        # Variáveis de ambiente esperadas (.env)
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.conta_corrente = os.getenv("CONTA_CORRENTE")
        self.cert_path = os.getenv("CERT_PATH")
        self.key_path = os.getenv("KEY_PATH")

    def emitir_boleto(self, cliente_dict: Dict[str, Any], data_venc: dt.date) -> Dict[str, Any]:
        """Tenta usar seu emitir_boletos.py. Se não houver, simula."""
        if _emit_mod and hasattr(_emit_mod, "emitir_boleto"):
            # Espera-se que você disponibilize uma função assim no seu script.
            # Adapte aqui conforme sua assinatura real.
            return _emit_mod.emitir_boleto(
                cliente=cliente_dict,
                data_vencimento=data_venc,
                client_id=self.client_id,
                client_secret=self.client_secret,
                conta_corrente=self.conta_corrente,
                cert_path=self.cert_path,
                key_path=self.key_path,
            )
        # ------- Modo simulado -------
        import uuid
        nn = uuid.uuid4().hex[:12].upper()
        return {
            "nossoNumero": nn,
            "linhaDigitavel": f"23790.00000 {nn[:5]}.000000 00000.{nn[5:10]} 0 00000000000000",
            "codigoBarras": f"2379{nn}000000000000",
            "txId": uuid.uuid4().hex,
            "pdfBytes": None,  # será baixado em seguida se disponível
        }

    def baixar_pdf(self, identificador: str, *, campo: str = "nosso_numero") -> Optional[bytes]:
        if not identificador:
            return None
        if _baixar_mod and hasattr(_baixar_mod, "baixar_pdf"):
            try:
                return _baixar_mod.baixar_pdf(
                    nosso_numero=identificador if campo != "codigo_solicitacao" else "",
                    codigo_solicitacao=identificador if campo == "codigo_solicitacao" else "",
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    conta_corrente=self.conta_corrente,
                    cert_path=self.cert_path,
                    key_path=self.key_path,
                )
            except TypeError:
                return _baixar_mod.baixar_pdf(
                    nosso_numero=identificador,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    conta_corrente=self.conta_corrente,
                    cert_path=self.cert_path,
                    key_path=self.key_path,
                )
        # Sem integração: sem PDF
        return None

    def cancelar_boleto(self, nosso_numero: str) -> bool:
        # TODO: Evoluir para chamar a API oficial do Inter para baixa/cancelamento.
        # Por ora, retornamos True apenas para marcar no sistema.
        return True
