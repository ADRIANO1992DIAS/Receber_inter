
from django.db import models

from .constants import DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE, LEGACY_WHATSAPP_SAUDACAO_TEMPLATES

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
    ativo = models.BooleanField('Ativo', default=True)
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
    STATUS_NOVO = "novo"
    STATUS_EMITIDO = "emitido"
    STATUS_PAGO = "pago"
    STATUS_CANCELADO = "cancelado"
    STATUS_ERRO = "erro"
    STATUS_ATRASADO = "atrasado"
    STATUS_CHOICES = [
        (STATUS_NOVO, "Novo"),
        (STATUS_EMITIDO, "Emitido"),
        (STATUS_PAGO, "Pago"),
        (STATUS_CANCELADO, "Cancelado"),
        (STATUS_ERRO, "Erro"),
        (STATUS_ATRASADO, "Atrasado"),
    ]
    FORMA_PAGAMENTO_CHOICES = [
        ("", "Nao informado"),
        ("pix", "PIX"),
        ("dinheiro", "Dinheiro"),
    ]
    WHATSAPP_STATUS_PENDENTE = "pendente"
    WHATSAPP_STATUS_ENVIADO = "enviado"
    WHATSAPP_STATUS_ERRO = "erro"
    WHATSAPP_STATUS_CHOICES = [
        (WHATSAPP_STATUS_PENDENTE, "A enviar"),
        (WHATSAPP_STATUS_ENVIADO, "Enviado"),
        (WHATSAPP_STATUS_ERRO, "Erro"),
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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NOVO)
    erro_msg = models.TextField(blank=True)
    pdf = models.FileField(upload_to='boletos/', blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_PAGAMENTO_CHOICES,
        blank=True,
        default="",
    )
    whatsapp_status = models.CharField(
        max_length=20,
        choices=WHATSAPP_STATUS_CHOICES,
        default=WHATSAPP_STATUS_PENDENTE,
        blank=True,
    )
    whatsapp_status_detail = models.TextField(blank=True)
    whatsapp_status_updated_at = models.DateTimeField(blank=True, null=True)

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


class WhatsappConfig(models.Model):
    saudacao_template = models.TextField(default=DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracao de WhatsApp"
        verbose_name_plural = "Configuracoes de WhatsApp"

    def __str__(self):
        return "Configuracao principal do WhatsApp"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"saudacao_template": DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE},
        )
        if obj.saudacao_template in LEGACY_WHATSAPP_SAUDACAO_TEMPLATES:
            obj.saudacao_template = DEFAULT_WHATSAPP_SAUDACAO_TEMPLATE
            obj.save(update_fields=["saudacao_template"])
        return obj
