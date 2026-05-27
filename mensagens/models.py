from django.db import models
from django.contrib.auth.models import User
import json

class Conversa(models.Model):
    """Modelo para conversas criptografadas"""
    remetente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversas_enviadas')
    destinatario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversas_recebidas')
    chave_publica_remetente = models.TextField(help_text="Chave pública do remetente em JSON")
    chave_publica_destinatario = models.TextField(help_text="Chave pública do destinatário em JSON")
    parametros_dh = models.TextField(help_text="Parâmetros Diffie-Hellman em JSON")
    chave_sessao = models.BinaryField(null=True, blank=True, help_text="Chave de sessão criptografada")
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"Conversa {self.id}: {self.remetente} -> {self.destinatario}"
    
    def set_parametros_dh(self, params_dict):
        """Salva parâmetros DH como JSON"""
        self.parametros_dh = json.dumps(params_dict)
    
    def get_parametros_dh(self):
        """Recupera parâmetros DH"""
        return json.loads(self.parametros_dh)
    
    def set_chave_publica(self, tipo, chave_dict):
        """Salva chave pública como JSON"""
        if tipo == 'remetente':
            self.chave_publica_remetente = json.dumps(chave_dict)
        else:
            self.chave_publica_destinatario = json.dumps(chave_dict)
    
    def get_chave_publica(self, tipo):
        """Recupera chave pública"""
        data = self.chave_publica_remetente if tipo == 'remetente' else self.chave_publica_destinatario
        return json.loads(data) if data else None


class Mensagem(models.Model):
    """Modelo para mensagens criptografadas"""
    TIPOS = [
        ('TEXTO', 'Texto'),
        ('IMAGEM', 'Imagem'),
        ('AUDIO', 'Áudio'),
        ('VIDEO', 'Vídeo'),
    ]
    
    ALGORITMOS = [
        ('RSA', 'RSA-1024'),
        ('ELGAMAL', 'ElGamal-1024'),
        ('ECC', 'ECC-P128'),
        ('HIBRIDO', 'Híbrido'),
    ]
    
    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='TEXTO')
    algoritmo = models.CharField(max_length=10, choices=ALGORITMOS, default='HIBRIDO')
    conteudo_cifrado = models.BinaryField(help_text="Conteúdo criptografado")
    hash_integridade = models.CharField(max_length=128, help_text="Hash SHA-256/SHA3-512 para integridade")
    assinatura = models.BinaryField(null=True, blank=True, help_text="Assinatura digital")
    nonce = models.BinaryField(help_text="Nonce de 128 bits")
    metadados = models.TextField(default='{}', help_text="Metadados em JSON")
    enviado_em = models.DateTimeField(auto_now_add=True)
    recebido_em = models.DateTimeField(null=True, blank=True)
    lido = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['enviado_em']
    
    def __str__(self):
        return f"Mensagem {self.id}: {self.tipo} - {self.algoritmo}"
    
    def set_metadados(self, meta_dict):
        """Salva metadados como JSON"""
        self.metadados = json.dumps(meta_dict)
    
    def get_metadados(self):
        """Recupera metadados"""
        return json.loads(self.metadados)


class Certificado(models.Model):
    """Modelo para certificados digitais (PKI)"""
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    chave_publica = models.TextField(help_text="Chave pública em formato PEM")
    emitido_por = models.CharField(max_length=100, default="CA-Sistema-Mensagens")
    numero_serie = models.CharField(max_length=64, unique=True)
    valido_de = models.DateTimeField()
    valido_ate = models.DateTimeField()
    assinatura_ca = models.BinaryField(help_text="Assinatura da CA")
    revogado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Certificado de {self.usuario.username}"
    
    def is_valido(self):
        """Verifica se certificado está válido"""
        from django.utils import timezone
        agora = timezone.now()
        return self.valido_de <= agora <= self.valido_ate and not self.revogado