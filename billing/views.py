import base64
import calendar
import datetime as dt
import io
import unicodedata
import zipfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional, List, Set, Dict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import FileResponse, HttpResponseNotFound, HttpResponse
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.utils.text import slugify

from openpyxl import load_workbook, Workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import Cliente, Boleto
from .forms import SelecionarClientesForm, ClienteForm, BoletoForm, ClienteImportForm
from .services.inter_service import InterService


MESES_CHOICES = [
    (1, "Janeiro"),
    (2, "Fevereiro"),
    (3, "Marco"),
    (4, "Abril"),
    (5, "Maio"),
    (6, "Junho"),
    (7, "Julho"),
    (8, "Agosto"),
    (9, "Setembro"),
    (10, "Outubro"),
    (11, "Novembro"),
    (12, "Dezembro"),
]

CLIENTE_IMPORT_HEADER_ALIASES: Dict[str, str] = {
    "nome": "nome",
    "cliente": "nome",
    "razaosocial": "nome",
    "cpfcnpj": "cpfCnpj",
    "cpf": "cpfCnpj",
    "cnpj": "cpfCnpj",
    "documento": "cpfCnpj",
    "valornominal": "valorNominal",
    "valor": "valorNominal",
    "valorbruto": "valorNominal",
    "datavencimento": "dataVencimento",
    "vencimento": "dataVencimento",
    "diavencimento": "dataVencimento",
    "diadovencimento": "dataVencimento",
    "dia": "dataVencimento",
    "email": "email",
    "ddd": "ddd",
    "telefone": "telefone",
    "celular": "telefone",
    "endereco": "endereco",
    "logradouro": "endereco",
    "numero": "numero",
    "complemento": "complemento",
    "bairro": "bairro",
    "cidade": "cidade",
    "municipio": "cidade",
    "uf": "uf",
    "estado": "uf",
    "cep": "cep",
}

CLIENTE_IMPORT_REQUIRED = {"nome", "cpfCnpj", "valorNominal", "dataVencimento"}


def _normalizar_header(valor: Optional[str]) -> str:
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
    return "".join(ch for ch in texto if ch.isalnum())


def _texto_limpo(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor.strip()
    return str(valor).strip()


def _apenas_digitos(valor: str) -> str:
    return "".join(ch for ch in valor if ch.isdigit())


def _parse_decimal(valor) -> Decimal:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError("Valor nominal ausente.")

    if isinstance(valor, Decimal):
        decimal_valor = valor
    elif isinstance(valor, (int, float)):
        decimal_valor = Decimal(str(valor))
    else:
        texto = str(valor)
        texto = texto.replace("R$", "").replace(" ", "")
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            texto = texto.replace(",", ".")
        decimal_valor = Decimal(texto)

    return decimal_valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_dia_vencimento(valor) -> int:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError("Campo dataVencimento ausente.")

    if isinstance(valor, dt.date):
        dia = valor.day
    elif isinstance(valor, (int, float, Decimal)):
        dia = int(valor)
    else:
        texto = str(valor).strip()
        if not texto:
            raise ValueError("Campo dataVencimento vazio.")
        dia = int(float(texto.replace(",", ".")))

    if not 1 <= dia <= 31:
        raise ValueError("Campo dataVencimento deve estar entre 1 e 31.")
    return dia


def _arquivo_pdf_nome(boleto: Boleto) -> str:
    competencia = f"{boleto.competencia_mes:02d}-{boleto.competencia_ano}"
    base = f"{boleto.cliente.nome}-{competencia}-{boleto.id}"
    slug = slugify(base)
    if not slug:
        slug = f"boleto-{boleto.id}"
    return f"{slug}.pdf"


def _buscar_pdf_bytes(inter: InterService, boleto: Boleto) -> Optional[bytes]:
    if boleto.pdf:
        with boleto.pdf.open("rb") as stream:
            return stream.read()

    identificadores = [
        (boleto.nosso_numero, "nosso_numero"),
        (boleto.codigo_solicitacao, "codigo_solicitacao"),
    ]
    for ident, campo in identificadores:
        if not ident:
            continue
        pdf_bytes = inter.baixar_pdf(ident, campo=campo)
        if pdf_bytes:
            if isinstance(pdf_bytes, str):
                pdf_bytes = base64.b64decode(pdf_bytes)
            return pdf_bytes
    return None


def home(request):
    # Agora a raiz (/) redireciona para a lista de clientes
    return redirect("clientes_list")


@login_required
def clientes_list(request):
    clientes = Cliente.objects.all().order_by("nome")
    return render(request, "billing/clientes_list.html", {"clientes": clientes})


@login_required
def cliente_import(request):
    form = ClienteImportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        arquivo = form.cleaned_data["arquivo"]
        arquivo.seek(0)

        try:
            workbook = load_workbook(arquivo, data_only=True)
        except InvalidFileException:
            form.add_error("arquivo", "O arquivo deve estar em formato Excel (.xlsx).")
        except Exception as exc:
            form.add_error("arquivo", f"Não foi possível ler a planilha: {exc}")
        else:
            try:
                sheet = workbook.active
                header_row = next(sheet.iter_rows(max_row=1, values_only=True), None)
                if not header_row:
                    form.add_error("arquivo", "A planilha precisa ter uma linha de cabeçalho.")
                else:
                    header_map: Dict[str, int] = {}
                    for idx, header in enumerate(header_row):
                        campo = CLIENTE_IMPORT_HEADER_ALIASES.get(_normalizar_header(header))
                        if campo and campo not in header_map:
                            header_map[campo] = idx

                    campos_faltando = [campo for campo in CLIENTE_IMPORT_REQUIRED if campo not in header_map]
                    if campos_faltando:
                        cabecalhos = ", ".join(sorted(campos_faltando))
                        form.add_error("arquivo", f"Cabeçalhos obrigatórios ausentes: {cabecalhos}.")
                    else:
                        criados = atualizados = 0
                        erros: List[str] = []

                        for linha_idx, row in enumerate(
                            sheet.iter_rows(min_row=2, values_only=True),
                            start=2,
                        ):
                            if row is None:
                                continue

                            if all(
                                cell is None or (isinstance(cell, str) and not cell.strip())
                                for cell in row
                            ):
                                continue

                            dados = {
                                campo: (row[idx] if idx < len(row) else None)
                                for campo, idx in header_map.items()
                            }

                            try:
                                nome = _texto_limpo(dados.get("nome"))
                                if not nome:
                                    raise ValueError("Nome não informado.")
                                cpf = _apenas_digitos(_texto_limpo(dados.get("cpfCnpj")))
                                if not cpf:
                                    raise ValueError("CPF/CNPJ não informado.")
                                valor_nominal = _parse_decimal(dados.get("valorNominal"))
                                dia_venc = _parse_dia_vencimento(dados.get("dataVencimento"))
                            except (ValueError, InvalidOperation) as exc:
                                erros.append(f"Linha {linha_idx}: {exc}")
                                continue

                            defaults = {
                                "nome": nome,
                                "valorNominal": valor_nominal,
                                "dataVencimento": dia_venc,
                                "email": _texto_limpo(dados.get("email")),
                                "ddd": _texto_limpo(dados.get("ddd")),
                                "telefone": _texto_limpo(dados.get("telefone")),
                                "endereco": _texto_limpo(dados.get("endereco")),
                                "numero": _texto_limpo(dados.get("numero")),
                                "complemento": _texto_limpo(dados.get("complemento")),
                                "bairro": _texto_limpo(dados.get("bairro")),
                                "cidade": _texto_limpo(dados.get("cidade")),
                                "uf": _texto_limpo(dados.get("uf")).upper(),
                                "cep": _texto_limpo(dados.get("cep")),
                            }

                            cliente, criado = Cliente.objects.update_or_create(
                                cpfCnpj=cpf,
                                defaults=defaults,
                            )

                            if criado:
                                criados += 1
                            else:
                                atualizados += 1

                        if criados or atualizados:
                            mensagens = []
                            if criados:
                                mensagens.append(f"{criados} cliente(s) novo(s)")
                            if atualizados:
                                mensagens.append(f"{atualizados} cliente(s) atualizado(s)")
                            resumo = ", ".join(mensagens)
                            messages.success(
                                request,
                                f"Importação concluída com sucesso: {resumo}.",
                            )
                        else:
                            messages.info(
                                request,
                                "Nenhum cliente foi criado ou atualizado. Verifique os dados da planilha.",
                            )

                        if erros:
                            resumo_erros = "; ".join(erros[:5])
                            if len(erros) > 5:
                                resumo_erros += f"; ... (+{len(erros) - 5} linha(s) com erro)"
                            messages.warning(
                                request,
                                f"Algumas linhas foram ignoradas: {resumo_erros}",
                            )

                        return redirect("clientes_list")
            finally:
                workbook.close()

    return render(request, "billing/cliente_import.html", {"form": form})


@login_required
def cliente_import_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    ws.append(
        [
            "Nome",
            "CPF/CNPJ",
            "Valor nominal",
            "dataVencimento",
            "E-mail",
            "DDD",
            "Telefone",
            "Endereco",
            "Numero",
            "Complemento",
            "Bairro",
            "Cidade",
            "UF",
            "CEP",
        ]
    )
    ws.append(
        [
            "Empresa Exemplo Ltda",
            "12.345.678/0001-90",
            199.9,
            10,
            "contato@exemplo.com",
            "11",
            "99999-1111",
            "Rua das Flores",
            "123",
            "Sala 12",
            "Centro",
            "Sao Paulo",
            "SP",
            "01000-000",
        ]
    )
    ws.append(
        [
            "Cliente Pessoa Física",
            "123.456.789-00",
            89.5,
            25,
            "cliente@email.com",
            "21",
            "98888-2222",
            "Av. Atlantica",
            "456",
            "",
            "Copacabana",
            "Rio de Janeiro",
            "RJ",
            "22010-000",
        ]
    )

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="clientes_modelo.xlsx"'
    wb.save(response)
    return response


@login_required
def cliente_create(request):
    form = ClienteForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Cliente cadastrado com sucesso.")
        return redirect("clientes_list")
    return render(request, "billing/cliente_form.html", {"form": form, "titulo": "Novo cliente"})


@login_required
def cliente_update(request, cliente_id: int):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    form = ClienteForm(request.POST or None, instance=cliente)
    if form.is_valid():
        form.save()
        messages.success(request, "Cliente atualizado com sucesso.")
        return redirect("clientes_list")
    return render(request, "billing/cliente_form.html", {"form": form, "titulo": f"Editar {cliente.nome}"})


@login_required
def cliente_delete(request, cliente_id: int):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        cliente.delete()
        messages.success(request, "Cliente removido.")
        return redirect("clientes_list")
    return render(request, "billing/cliente_confirm_delete.html", {"cliente": cliente})


@login_required
def boletos_list(request):
    boletos = Boleto.objects.select_related("cliente").order_by("-criado_em")

    mes_param = request.GET.get("mes", "").strip()
    ano_param = request.GET.get("ano", "").strip()
    status_param = request.GET.get("status", "").strip()

    mes_selecionado = ""
    if mes_param:
        try:
            mes_valor = int(mes_param)
        except ValueError:
            mes_valor = None
        if mes_valor and 1 <= mes_valor <= 12:
            boletos = boletos.filter(competencia_mes=mes_valor)
            mes_selecionado = str(mes_valor)

    ano_selecionado = ""
    if ano_param:
        try:
            ano_valor = int(ano_param)
        except ValueError:
            ano_valor = None
        if ano_valor:
            boletos = boletos.filter(competencia_ano=ano_valor)
            ano_selecionado = str(ano_valor)

    status_choices_map = dict(Boleto.STATUS_CHOICES)
    status_opcoes = [
        {"value": "", "label": "Todos"},
    ] + [
        {"value": value, "label": label} for value, label in Boleto.STATUS_CHOICES
    ]

    status_selecionado = ""
    if status_param and status_param in status_choices_map:
        boletos = boletos.filter(status=status_param)
        status_selecionado = status_param

    anos_disponiveis = list(
        Boleto.objects.order_by("-competencia_ano")
        .values_list("competencia_ano", flat=True)
        .distinct()
    )

    meses_contexto = [{"value": "", "label": "Todos"}] + [
        {"value": str(valor), "label": nome} for valor, nome in MESES_CHOICES
    ]

    context = {
        "boletos": boletos,
        "meses": meses_contexto,
        "anos": [str(ano) for ano in anos_disponiveis],
        "mes_selecionado": mes_selecionado,
        "ano_selecionado": ano_selecionado,
        "status_opcoes": status_opcoes,
        "status_selecionado": status_selecionado,
    }
    return render(request, "billing/boletos_list.html", context)


@login_required
def boleto_create(request):
    form = BoletoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        boleto = form.save()
        messages.success(request, f"Boleto criado para {boleto.cliente.nome}.")
        return redirect("boletos_list")
    return render(request, "billing/boleto_form.html", {"form": form, "titulo": "Novo boleto"})


@login_required
def boleto_update(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    form = BoletoForm(request.POST or None, request.FILES or None, instance=boleto)
    if form.is_valid():
        boleto = form.save()
        messages.success(request, f"Boleto atualizado para {boleto.cliente.nome}.")
        return redirect("boletos_list")
    return render(request, "billing/boleto_form.html", {"form": form, "titulo": f"Editar boleto #{boleto.id}"})


@login_required
def boleto_delete(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    if request.method == "POST":
        boleto.delete()
        messages.success(request, "Boleto removido.")
        return redirect("boletos_list")
    return render(request, "billing/boleto_confirm_delete.html", {"boleto": boleto})


@login_required
def gerar_boletos(request):
    form = SelecionarClientesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ano = form.cleaned_data["ano"]
        mes = form.cleaned_data["mes"]
        clientes = form.cleaned_data["clientes"]
        inter = InterService()

        with transaction.atomic():
            for cli in clientes:
                # Calcula data de vencimento (ajustando para ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âºltimo dia do mÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âªs, se necessÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡rio)
                last_day = calendar.monthrange(ano, mes)[1]
                dia = min(cli.dataVencimento, last_day)
                data_venc = dt.date(ano, mes, dia)

                # Evita duplicidade da mesma competÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âªncia
                boleto, created = Boleto.objects.get_or_create(
                    cliente=cli, competencia_ano=ano, competencia_mes=mes,
                    defaults={
                        "data_vencimento": data_venc,
                        "valor": cli.valorNominal,
                    }
                )
                if not created:
                    messages.info(request, f"Boleto jÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡ existia: {cli.nome} {mes:02d}/{ano}")
                    continue

                # Monta dict no formato esperado pelo serviÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§o (Banco Inter)
                cli_dict = {
                    "valorNominal": float(cli.valorNominal),
                    "nome": cli.nome,
                    "cpfCnpj": cli.cpfCnpj,
                    "email": cli.email,
                    "ddd": cli.ddd,
                    "telefone": cli.telefone,
                    "endereco": cli.endereco,
                    "numero": cli.numero,
                    "complemento": cli.complemento,
                    "bairro": cli.bairro,
                    "cidade": cli.cidade,
                    "uf": cli.uf,
                    "cep": cli.cep,
                }
                try:
                    result = inter.emitir_boleto(cli_dict, data_venc)
                    boleto.nosso_numero = result.get("nossoNumero","")
                    boleto.linha_digitavel = result.get("linhaDigitavel","")
                    boleto.codigo_barras = result.get("codigoBarras","")
                    boleto.tx_id = result.get("txId","")
                    boleto.codigo_solicitacao = result.get("codigoSolicitacao","")
                    boleto.status = "emitido"
                    boleto.save()

                    # tenta baixar PDF logo apÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³s emitir
                    identificadores = [
                        (boleto.nosso_numero, "nosso_numero"),
                        (boleto.codigo_solicitacao, "codigo_solicitacao"),
                    ]
                    pdf_bytes = None
                    for ident, campo in identificadores:
                        if not ident:
                            continue
                        pdf_bytes = inter.baixar_pdf(ident, campo=campo)
                        if pdf_bytes:
                            break
                    if pdf_bytes:
                        if isinstance(pdf_bytes, str):
                            pdf_bytes = base64.b64decode(pdf_bytes)
                        from django.core.files.base import ContentFile
                        boleto.pdf.save(f"boleto_{boleto.id}.pdf", ContentFile(pdf_bytes))
                        boleto.save()

                except Exception as e:
                    boleto.status = "erro"
                    boleto.erro_msg = str(e)
                    boleto.save()
                    messages.error(request, f"Erro ao emitir boleto de {cli.nome}: {e}")

            messages.success(request, "Processo de emissÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â£o finalizado.")
        return redirect("boletos_list")

    return render(request, "billing/gerar_boletos.html", {"form": form})

@login_required
def baixar_pdf_view(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    inter = InterService()
    pdf_bytes = _buscar_pdf_bytes(inter, boleto)
    if not pdf_bytes:
        return HttpResponseNotFound("PDF nao disponivel.")

    if not boleto.pdf:
        filename = _arquivo_pdf_nome(boleto)
        boleto.pdf.save(filename, ContentFile(pdf_bytes))
        boleto.save(update_fields=["pdf"])

    stored_name = Path(boleto.pdf.name).name if boleto.pdf else _arquivo_pdf_nome(boleto)
    return FileResponse(
        boleto.pdf.open("rb"),
        as_attachment=True,
        filename=stored_name,
    )


@login_required
def baixar_pdf_lote(request):
    if request.method != "POST":
        messages.info(request, "Selecione os boletos desejados e use o botao de download.")
        return redirect("boletos_list")

    ids = request.POST.getlist("boletos")
    if not ids:
        messages.info(request, "Selecione ao menos um boleto para baixar.")
        return redirect("boletos_list")

    boletos = list(Boleto.objects.filter(id__in=ids).select_related("cliente"))
    if not boletos:
        messages.error(request, "Nenhum boleto encontrado para os identificadores informados.")
        return redirect("boletos_list")

    inter = InterService()
    buffer = io.BytesIO()
    erros: List[str] = []
    nomes_utilizados: Set[str] = set()
    sucesso = 0

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_stream:
        for boleto in boletos:
            pdf_bytes = _buscar_pdf_bytes(inter, boleto)
            if not pdf_bytes:
                erros.append(f"Boleto {boleto.id} - {boleto.cliente.nome}")
                continue

            sucesso += 1
            if not boleto.pdf:
                filename = _arquivo_pdf_nome(boleto)
                boleto.pdf.save(filename, ContentFile(pdf_bytes))
                boleto.save(update_fields=["pdf"])

            stored_name = Path(boleto.pdf.name).name if boleto.pdf else _arquivo_pdf_nome(boleto)
            nome_zip = stored_name
            base_name = Path(stored_name).stem or f"boleto_{boleto.id}"
            extension = Path(stored_name).suffix or ".pdf"
            contador = 1
            while nome_zip in nomes_utilizados:
                nome_zip = f"{base_name}_{contador}{extension}"
                contador += 1
            nomes_utilizados.add(nome_zip)
            zip_stream.writestr(nome_zip, pdf_bytes)

        if erros:
            conteudo_erros = "Nao foi possivel obter o PDF dos seguintes boletos:\n" + "\n".join(erros)
            zip_stream.writestr("boletos_com_erro.txt", conteudo_erros)

    if sucesso == 0:
        messages.error(request, "Nao foi possivel baixar o PDF de nenhum boleto selecionado.")
        return redirect("boletos_list")

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=boletos_selecionados.zip"
    return response

@login_required
def marcar_pago(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    boleto.status = "pago"
    boleto.data_pagamento = dt.date.today()
    boleto.save()
    messages.success(request, "Baixa registrada no sistema.")
    return redirect("boletos_list")


@login_required
def cancelar_boleto(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    inter = InterService()
    try:
        resultado = inter.cancelar_boleto(
            codigo_solicitacao=boleto.codigo_solicitacao or "",
            nosso_numero=boleto.nosso_numero or "",
        )
    except Exception as exc:  # noqa: BLE001 - queremos exibir o motivo ao usuÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡rio
        boleto.erro_msg = str(exc)
        boleto.save(update_fields=["erro_msg"])
        messages.error(request, f"Falha ao cancelar via API: {exc}")
    else:
        boleto.status = "cancelado"
        boleto.erro_msg = ""
        boleto.save(update_fields=["status", "erro_msg"])
        situacao = resultado.get("situacao") or resultado.get("status")
        if situacao:
            messages.success(
                request,
                f"CobranÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§a cancelada. SituaÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â£o informada pelo Inter: {situacao}",
            )
        else:
            messages.success(request, "CobranÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§a cancelada com sucesso no Inter.")
    return redirect("boletos_list")
