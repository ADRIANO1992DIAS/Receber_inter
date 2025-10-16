
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("conciliacao/", views.conciliacao, name="conciliacao"),
    path("clientes/", views.clientes_list, name="clientes_list"),
    path("clientes/importar/", views.cliente_import, name="cliente_import"),
    path("clientes/importar/modelo/", views.cliente_import_template, name="cliente_import_template"),
    path("clientes/novo/", views.cliente_create, name="cliente_create"),
    path("clientes/<int:cliente_id>/editar/", views.cliente_update, name="cliente_update"),
    path("clientes/<int:cliente_id>/excluir/", views.cliente_delete, name="cliente_delete"),
    path("boletos/", views.boletos_list, name="boletos_list"),
    path("boletos/novo/", views.boleto_create, name="boleto_create"),
    path("boletos/<int:boleto_id>/editar/", views.boleto_update, name="boleto_update"),
    path("boletos/<int:boleto_id>/excluir/", views.boleto_delete, name="boleto_delete"),
    path("gerar/", views.gerar_boletos, name="gerar_boletos"),
    path("boletos/sincronizar/", views.sincronizar_boletos, name="sincronizar_boletos"),
    path("boletos/<int:boleto_id>/pdf/", views.baixar_pdf_view, name="baixar_pdf"),
    path("boletos/pdfs/", views.baixar_pdf_lote, name="baixar_pdf_lote"),
    path("boletos/<int:boleto_id>/pagar/", views.marcar_pago, name="marcar_pago"),
    path("boletos/<int:boleto_id>/pagar/pix/", views.marcar_pago_pix, name="marcar_pago_pix"),
    path("boletos/<int:boleto_id>/pagar/dinheiro/", views.marcar_pago_dinheiro, name="marcar_pago_dinheiro"),
    path("boletos/<int:boleto_id>/cancelar/", views.cancelar_boleto, name="cancelar_boleto"),
    path("enviaboleto/", views.enviar_boletos_whatsapp, name="enviar_boletos_whatsapp"),
    path("enviaboletos/", views.enviar_boletos_whatsapp, name="enviar_boletos_whatsapp_plural"),
]
