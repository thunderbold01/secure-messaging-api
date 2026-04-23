from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import datetime
import json

# Imports condicionais para evitar erros
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("AVISO: Cryptography não disponível. Instale: pip install cryptography")

Usuario = get_user_model()


class AutoridadeCertificadora(models.Model):
    """CA - Autoridade Certificadora raiz"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, unique=True)
    
    # Certificado da CA
    certificado_pem = models.TextField()
    chave_privada = models.TextField()  # Criptografada
    
    # Validade
    valido_de = models.DateTimeField()
    valido_ate = models.DateTimeField()
    
    # Configurações
    ativa = models.BooleanField(default=True)
    nivel = models.IntegerField(default=1)  # 1=Root, 2=Intermediate
    
    criada_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'autoridades_certificadoras'
        verbose_name = 'Autoridade Certificadora'
        verbose_name_plural = 'Autoridades Certificadoras'
    
    def __str__(self):
        return f"CA: {self.nome} (Nível {self.nivel})"
    
    @classmethod
    def criar_ca_raiz(cls, nome="SecureMessaging Root CA"):
        """Cria uma CA raiz auto-assinada"""
        if not CRYPTO_AVAILABLE:
            # Cria uma CA simulada para desenvolvimento
            return cls.objects.create(
                nome=nome,
                certificado_pem="CERTIFICADO_SIMULADO",
                chave_privada="CHAVE_SIMULADA",
                valido_de=timezone.now(),
                valido_ate=timezone.now() + datetime.timedelta(days=3650),
                nivel=1
            )
        
        # Gera chave RSA-4096 para a CA
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        
        # Cria certificado auto-assinado
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "SP"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Sao Paulo"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, nome),
            x509.NameAttribute(NameOID.COMMON_NAME, nome),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=3650)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Serializa
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
        key_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).decode()
        
        return cls.objects.create(
            nome=nome,
            certificado_pem=cert_pem,
            chave_privada=key_pem,
            valido_de=cert.not_valid_before,
            valido_ate=cert.not_valid_after,
            nivel=1
        )


class CertificadoDigital(models.Model):
    """Certificados digitais X.509 para usuários e serviços"""
    
    STATUS = [
        ('VALIDO', 'Válido'),
        ('REVOGADO', 'Revogado'),
        ('EXPIRADO', 'Expirado'),
        ('SUSPENSO', 'Suspenso'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dono do certificado
    usuario = models.OneToOneField(
        Usuario, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='certificado'
    )
    servico = models.CharField(max_length=100, null=True, blank=True)
    
    # Certificado X.509
    certificado_pem = models.TextField()
    chave_publica_pem = models.TextField()
    
    # Metadados do certificado
    serial_number = models.CharField(max_length=64, unique=True)
    subject = models.TextField()
    issuer = models.TextField()
    
    # Validade
    valido_de = models.DateTimeField()
    valido_ate = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS, default='VALIDO')
    data_revogacao = models.DateTimeField(null=True, blank=True)
    motivo_revogacao = models.TextField(null=True, blank=True)
    
    # Assinatura da CA
    assinado_por = models.ForeignKey(
        AutoridadeCertificadora, 
        on_delete=models.PROTECT,
        related_name='certificados_emitidos',
        null=True,
        blank=True
    )
    
    # Fingerprints
    fingerprint_sha256 = models.CharField(max_length=64, unique=True)
    fingerprint_sha1 = models.CharField(max_length=40)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'certificados_digitais'
        verbose_name = 'Certificado Digital'
        verbose_name_plural = 'Certificados Digitais'
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['fingerprint_sha256']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        if self.usuario:
            return f"Certificado de {self.usuario.username}"
        return f"Certificado de {self.servico}"
    
    def is_valido(self):
        """Verifica se o certificado está válido"""
        agora = timezone.now()
        return (
            self.status == 'VALIDO' and
            self.valido_de <= agora <= self.valido_ate
        )
    
    def revogar(self, motivo):
        """Revoga o certificado"""
        self.status = 'REVOGADO'
        self.data_revogacao = timezone.now()
        self.motivo_revogacao = motivo
        self.save()


class LogSeguranca(models.Model):
    """Logs de segurança e auditoria"""
    
    NIVEL = [
        ('INFO', 'Informação'),
        ('WARNING', 'Aviso'),
        ('ERROR', 'Erro'),
        ('CRITICAL', 'Crítico'),
        ('SECURITY', 'Segurança'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    nivel = models.CharField(max_length=10, choices=NIVEL)
    evento = models.CharField(max_length=100)
    descricao = models.TextField()
    
    # Origem
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Dados adicionais
    dados = models.JSONField(default=dict)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'logs_seguranca'
        verbose_name = 'Log de Segurança'
        verbose_name_plural = 'Logs de Segurança'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['nivel', 'timestamp']),
            models.Index(fields=['evento']),
            models.Index(fields=['usuario']),
        ]
    
    def __str__(self):
        return f"[{self.nivel}] {self.evento} - {self.timestamp}"