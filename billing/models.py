
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
    FORMA_PAGAMENTO_CHOICES = [
        ("", "Nao informado"),
        ("pix", "PIX"),
        ("dinheiro", "Dinheiro"),
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
    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_PAGAMENTO_CHOICES,
        blank=True,
        default="",
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cliente', 'competencia_ano', 'competencia_mes')

    def __str__(self):
        return f"Boleto {self.id} - {self.cliente.nome} {self.competencia_mes:02d}/{self.competencia_ano}"


class ConciliacaoLancamento(models.Model):
    hash_identificador = models.CharField(max_length=128, unique=True)
    data = models.DateField()
    descricao = models.CharField(max_length=255)
    descricao_chave = models.CharField(max_length=255, blank=True, db_index=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    boleto = models.ForeignKey(
        Boleto,
        on_delete=models.SET_NULL,
        related_name="conciliacoes",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-data", "-id")

    def __str__(self):
        referencia = f"{self.data:%d/%m/%Y} - {self.descricao}"
        if self.boleto_id:
            referencia += f" (Boleto #{self.boleto_id})"
        return referencia


class ConciliacaoAlias(models.Model):
    descricao_chave = models.CharField(max_length=255, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="conciliacao_aliases")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("descricao_chave",)

    def __str__(self):
        return f"{self.descricao_chave} -> {self.cliente.nome}"
