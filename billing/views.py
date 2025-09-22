import base64
import calendar
import datetime as dt

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import FileResponse, HttpResponseNotFound
from django.db import transaction
from django.contrib.auth.decorators import login_required

from .models import Cliente, Boleto
from .forms import SelecionarClientesForm, ClienteForm, BoletoForm
from .services.inter_service import InterService


def home(request):
    # Agora a raiz (/) redireciona para a lista de clientes
    return redirect("clientes_list")


@login_required
def clientes_list(request):
    clientes = Cliente.objects.all().order_by("nome")
    return render(request, "billing/clientes_list.html", {"clientes": clientes})


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
    return render(request, "billing/boletos_list.html", {"boletos": boletos})


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
                # Calcula data de vencimento (ajustando para último dia do mês, se necessário)
                last_day = calendar.monthrange(ano, mes)[1]
                dia = min(cli.dataVencimento, last_day)
                data_venc = dt.date(ano, mes, dia)

                # Evita duplicidade da mesma competência
                boleto, created = Boleto.objects.get_or_create(
                    cliente=cli, competencia_ano=ano, competencia_mes=mes,
                    defaults={
                        "data_vencimento": data_venc,
                        "valor": cli.valorNominal,
                    }
                )
                if not created:
                    messages.info(request, f"Boleto já existia: {cli.nome} {mes:02d}/{ano}")
                    continue

                # Monta dict no formato esperado pelo serviço (Banco Inter)
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

                    # tenta baixar PDF logo após emitir
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

            messages.success(request, "Processo de emissão finalizado.")
        return redirect("boletos_list")

    return render(request, "billing/gerar_boletos.html", {"form": form})


@login_required
def baixar_pdf_view(request, boleto_id: int):
    boleto = get_object_or_404(Boleto, id=boleto_id)
    if boleto.pdf:
        return FileResponse(boleto.pdf.open("rb"), as_attachment=True, filename=f"boleto_{boleto.id}.pdf")
    # tenta baixar caso não tenha sido salvo ainda
    inter = InterService()
    for identificador, campo in ((boleto.nosso_numero, "nosso_numero"), (boleto.codigo_solicitacao, "codigo_solicitacao")):
        if not identificador:
            continue
        pdf_bytes = inter.baixar_pdf(identificador, campo=campo)
        if pdf_bytes:
            if isinstance(pdf_bytes, str):
                pdf_bytes = base64.b64decode(pdf_bytes)
            from django.core.files.base import ContentFile
            boleto.pdf.save(f"boleto_{boleto.id}.pdf", ContentFile(pdf_bytes))
            boleto.save()
            return FileResponse(boleto.pdf.open("rb"), as_attachment=True, filename=f"boleto_{boleto.id}.pdf")
    return HttpResponseNotFound("PDF não disponível.")


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
    except Exception as exc:  # noqa: BLE001 - queremos exibir o motivo ao usuário
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
                f"Cobrança cancelada. Situação informada pelo Inter: {situacao}",
            )
        else:
            messages.success(request, "Cobrança cancelada com sucesso no Inter.")
    return redirect("boletos_list")
