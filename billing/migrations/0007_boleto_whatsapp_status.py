from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_whatsappconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="boleto",
            name="whatsapp_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pendente", "A enviar"),
                    ("enviado", "Enviado"),
                    ("erro", "Erro"),
                ],
                default="pendente",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="boleto",
            name="whatsapp_status_detail",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="boleto",
            name="whatsapp_status_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

