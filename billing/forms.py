
from django import forms

from .models import Cliente, Boleto

class SelecionarClientesForm(forms.Form):
    ano = forms.IntegerField(min_value=2000, max_value=2100, initial=2025, label="Ano")
    mes = forms.IntegerField(min_value=1, max_value=12, initial=9, label="Mês")
    clientes = forms.ModelMultipleChoiceField(
        queryset=Cliente.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Selecione os clientes para gerar boletos",
    )


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "nome",
            "cpfCnpj",
            "valorNominal",
            "dataVencimento",
            "email",
            "ddd",
            "telefone",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "cep",
        ]
        widgets = {
            "dataVencimento": forms.NumberInput(attrs={"min": 1, "max": 31}),
            "valorNominal": forms.NumberInput(attrs={"step": "0.01"}),
        }


class BoletoForm(forms.ModelForm):
    class Meta:
        model = Boleto
        fields = [
            "cliente",
            "competencia_ano",
            "competencia_mes",
            "data_vencimento",
            "valor",
            "status",
            "nosso_numero",
            "linha_digitavel",
            "codigo_barras",
            "tx_id",
            "codigo_solicitacao",
            "data_pagamento",
            "pdf",
        ]
        widgets = {
            "competencia_ano": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
            "competencia_mes": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "data_vencimento": forms.DateInput(attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "valor": forms.NumberInput(attrs={"step": "0.01"}),
        }


class ClienteImportForm(forms.Form):
    arquivo = forms.FileField(label="Planilha Excel (.xlsx)")
