# Generated manually to bootstrap tables for billing app.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valorNominal', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Valor nominal')),
                ('dataVencimento', models.PositiveSmallIntegerField(verbose_name='Dia do vencimento (1..31)')),
                ('nome', models.CharField(max_length=200, verbose_name='Nome')),
                ('cpfCnpj', models.CharField(max_length=18, verbose_name='CPF/CNPJ')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail')),
                ('ddd', models.CharField(blank=True, max_length=3, verbose_name='DDD')),
                ('telefone', models.CharField(blank=True, max_length=20, verbose_name='Telefone')),
                ('endereco', models.CharField(blank=True, max_length=200, verbose_name='Endereço')),
                ('numero', models.CharField(blank=True, max_length=20, verbose_name='Número')),
                ('complemento', models.CharField(blank=True, max_length=100, verbose_name='Complemento')),
                ('bairro', models.CharField(blank=True, max_length=100, verbose_name='Bairro')),
                ('cidade', models.CharField(blank=True, max_length=100, verbose_name='Cidade')),
                ('uf', models.CharField(blank=True, choices=[('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'), ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'), ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'), ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'), ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'), ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'), ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO')], max_length=2, verbose_name='UF')),
                ('cep', models.CharField(blank=True, max_length=9, verbose_name='CEP')),
            ],
        ),
        migrations.CreateModel(
            name='Boleto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('competencia_ano', models.PositiveSmallIntegerField()),
                ('competencia_mes', models.PositiveSmallIntegerField()),
                ('data_vencimento', models.DateField()),
                ('valor', models.DecimalField(decimal_places=2, max_digits=12)),
                ('nosso_numero', models.CharField(blank=True, max_length=64)),
                ('linha_digitavel', models.CharField(blank=True, max_length=100)),
                ('codigo_barras', models.CharField(blank=True, max_length=100)),
                ('tx_id', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('novo', 'Novo'), ('emitido', 'Emitido'), ('pago', 'Pago'), ('cancelado', 'Cancelado'), ('erro', 'Erro')], default='novo', max_length=10)),
                ('erro_msg', models.TextField(blank=True)),
                ('pdf', models.FileField(blank=True, null=True, upload_to='boletos/')),
                ('data_pagamento', models.DateField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='boletos', to='billing.cliente')),
            ],
            options={
                'unique_together': {('cliente', 'competencia_ano', 'competencia_mes')},
            },
        ),
    ]
