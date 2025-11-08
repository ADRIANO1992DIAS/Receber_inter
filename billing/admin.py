
from django.contrib import admin
from .models import Cliente, Boleto

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome","cpfCnpj","ativo","valorNominal","dataVencimento","email","telefone","cidade","uf")
    search_fields = ("nome","cpfCnpj","email","cidade")
    list_filter = ("uf","ativo")

@admin.register(Boleto)
class BoletoAdmin(admin.ModelAdmin):
    list_display = ("cliente","competencia_mes","competencia_ano","valor","status","nosso_numero","codigo_solicitacao","data_vencimento")
    list_filter = ("status","competencia_ano","competencia_mes")
    search_fields = ("cliente__nome","nosso_numero","linha_digitavel","codigo_solicitacao")
