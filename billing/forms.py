from django import forms
from django.db.models import QuerySet
from django.utils import timezone

from .models import Cliente, Boleto


def _coerce_int_or_none(value):
    if value in (None, "", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SelecionarClientesForm(forms.Form):
    ano = forms.IntegerField(
        min_value=2000,
        max_value=2100,
        initial=2025,
        label="Ano",
        widget=forms.NumberInput(
            attrs={"min": 2000, "max": 2100, "style": "appearance:auto;"}
        ),
    )
    mes = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=9,
        label="Mes",
        widget=forms.NumberInput(
            attrs={"min": 1, "max": 12, "style": "appearance:auto;"}
        ),
    )
    dia = forms.TypedChoiceField(
        required=False,
        coerce=_coerce_int_or_none,
        choices=[],
        label="Filtrar por dia do vencimento",
    )
    clientes = forms.ModelMultipleChoiceField(
        queryset=Cliente.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Selecione os clientes para gerar boletos",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound:
            hoje = timezone.localdate()
            if hoje:
                self.initial.setdefault("ano", hoje.year)
                self.initial.setdefault("mes", hoje.month)
            self.fields["ano"].initial = self.initial.get("ano", self.fields["ano"].initial)
            self.fields["mes"].initial = self.initial.get("mes", self.fields["mes"].initial)

        clientes_qs = Cliente.objects.all()

        dias_disponiveis = (
            clientes_qs.order_by("dataVencimento")
            .values_list("dataVencimento", flat=True)
            .distinct()
        )
        choices = [("", "Todos os vencimentos")]
        choices.extend((str(dia), f"Dia {dia:02d}") for dia in dias_disponiveis)
        self.fields["dia"].choices = choices

        dia_raw = (
            self.data.get(self.add_prefix("dia"))
            if self.is_bound
            else self.initial.get("dia")
        )
        dia_filtrado = _coerce_int_or_none(dia_raw)

        if dia_filtrado:
            clientes_qs = clientes_qs.filter(dataVencimento=dia_filtrado)
            self.initial["dia"] = dia_filtrado
            self.fields["dia"].initial = str(dia_filtrado)
        elif not self.is_bound and "dia" not in self.initial:
            self.fields["dia"].initial = ""

        self.filtered_clientes = clientes_qs.order_by("nome")
        self.fields["clientes"].queryset = self.filtered_clientes
        self.fields["clientes"].label_from_instance = self._formatar_label

        selected_ids = set()
        if self.is_bound:
            data = getattr(self.data, "getlist", None)
            if callable(data):
                selected_ids = {str(val) for val in self.data.getlist(self.add_prefix("clientes"))}
            else:
                raw = self.data.get(self.add_prefix("clientes"))
                if raw:
                    if isinstance(raw, (list, tuple, set)):
                        selected_ids = {str(val) for val in raw}
                    else:
                        selected_ids = {str(raw)}
        else:
            initial = self.initial.get("clientes")
            if initial:
                if isinstance(initial, (list, tuple, set, QuerySet)):
                    selected_ids = {str(getattr(val, "pk", val)) for val in initial}
                else:
                    selected_ids = {str(getattr(initial, "pk", initial))}
        self.selected_cliente_ids = selected_ids

    @staticmethod
    def _formatar_label(cliente: Cliente) -> str:
        return (
            f"{cliente.nome} - CNPJ: {cliente.cpfCnpj} - "
            f"Vencimento dia {cliente.dataVencimento:02d}"
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
