
from django.db import models

UF_CHOICES = [
    ('AC','AC'),('AL','AL'),('AP','AP'),('AM','AM'),('BA','BA'),('CE','CE'),
    ('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),('MT','MT'),('MS','MS'),
    ('MG','MG'),('PA','PA'),('PB','PB'),('PR','PR'),('PE','PE'),('PI','PI'),
    ('RJ','RJ'),('RN','RN'),('RS','RS'),('RO','RO'),('RR','RR'),('SC','SC'),
    ('SP','SP'),('SE','SE'),('TO','TO'),
]

class Cliente(models.Model):
    valorNominal = models.DecimalField('Valor nominal', max_digits=12, decimal_places=2)
    dataVencimento = models.PositiveSmallIntegerField('Dia do vencimento (1..31)')
    nome = models.CharField('Nome', max_length=200)
    cpfCnpj = models.CharField('CPF/CNPJ', max_length=18)
    email = models.EmailField('E-mail', blank=True)
    ddd = models.CharField('DDD', max_length=3, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    endereco = models.CharField('Endereço', max_length=200, blank=True)
    numero = models.CharField('Número', max_length=20, blank=True)
    complemento = models.CharField('Complemento', max_length=100, blank=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True)
    uf = models.CharField('UF', max_length=2, choices=UF_CHOICES, blank=True)
    cep = models.CharField('CEP', max_length=9, blank=True)

    def __str__(self):
        return f"{self.nome} ({self.cpfCnpj})"


class Boleto(models.Model):
    STATUS_CHOICES = [
        ('novo', 'Novo'),
        ('emitido', 'Emitido'),
        ('pago', 'Pago'),
        ('cancelado', 'Cancelado'),
        ('erro', 'Erro'),
        ('atrasado', 'Atrasado'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='boletos')
    competencia_ano = models.PositiveSmallIntegerField()
    competencia_mes = models.PositiveSmallIntegerField()
    data_vencimento = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    nosso_numero = models.CharField(max_length=64, blank=True)
    linha_digitavel = models.CharField(max_length=100, blank=True)
    codigo_barras = models.CharField(max_length=100, blank=True)
    tx_id = models.CharField(max_length=100, blank=True)
    codigo_solicitacao = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='novo')
    erro_msg = models.TextField(blank=True)
    pdf = models.FileField(upload_to='boletos/', blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cliente', 'competencia_ano', 'competencia_mes')

    def __str__(self):
        return f"Boleto {self.id} - {self.cliente.nome} {self.competencia_mes:02d}/{self.competencia_ano}"
