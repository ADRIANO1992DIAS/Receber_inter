from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="boleto",
            name="codigo_solicitacao",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
