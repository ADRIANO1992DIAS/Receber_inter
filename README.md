# Contas a Receber + Boletos (Banco Inter) — Django

Projeto simples (início) para:
- Cadastrar clientes
- Selecionar clientes e gerar boletos (mensais) usando **dia de vencimento** de cada cliente
- Baixar PDF do boleto
- Marcar baixa (pago) manualmente
- Cancelar cobrança (marca como cancelado; hook pronto para evoluir e chamar API Inter)

> Interface minimalista por enquanto. Depois evoluiremos com Tailwind.

## Rodar com Docker Desktop

```bash
docker compose up --build -d
# Acesse: http://localhost:8000
# Admin: http://localhost:8000/admin/
```
No primeiro start o sistema cria o superusuário a partir das variáveis no `.env`.

## Credenciais (.env)

Preencha as variáveis no `.env`:
```
CLIENT_ID=
CLIENT_SECRET=
CONTA_CORRENTE=
CERT_PATH=Inter_API_Certificado.crt
KEY_PATH=Inter_API_Chave.key

DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=adriano92dias@outlook.com
DJANGO_SUPERUSER_PASSWORD=1585kdje
```

## Reutilizando seus scripts

Coloque seus arquivos dentro de `inter_api/` (crie a pasta ao lado do `manage.py`):
- `inter_api/emitir_boletos.py`
- `inter_api/baixar_boletos_pdf.py`

Assinaturas esperadas (adapte se necessário dentro de `billing/services/inter_service.py`):

```python
# emitir_boletos.py
def emitir_boleto_unico(cliente: dict, data_vencimento, client_id, client_secret, conta_corrente, cert_path, key_path) -> dict:
    return {
      "nossoNumero": "...",
      "linhaDigitavel": "...",
      "codigoBarras": "...",
      "txId": "...",
      "pdfBytes": b"...? (opcional)"
    }

# baixar_boletos_pdf.py
def baixar_pdf_por_nosso_numero(nosso_numero: str, client_id, client_secret, conta_corrente, cert_path, key_path) -> bytes:
    return b"%PDF..."  # conteúdo do PDF
```

Se esses módulos não existirem, o sistema **simula** a emissão (gera um `nossoNumero` fake) e não baixa PDF.

## Fluxo

1. Cadastre clientes em **/admin** ou na tela simples de clientes
2. Vá em **/gerar**, escolha ano e mês e selecione os clientes que deseja gerar boleto
3. Acompanhe em **/boletos** — baixe PDF, marque como pago, cancele

## Observações

- Banco de dados: SQLite (persistido em `./data/db.sqlite3` via volume do Docker)
- PDFs salvos em `./media/boletos/`
- Cancelamento: integração real via `InterService.cancelar_boleto`, usando `codigoSolicitacao` (ou `nossoNumero` como fallback) para chamar a API do Banco Inter.
- Na tela de boletos é possível marcar vários registros e baixar todos os PDFs em um único arquivo `.zip`.
