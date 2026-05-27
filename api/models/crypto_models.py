from django.db import models
from django.contrib.auth.models import User
import uuid

class ChaveCriptografica(models.Model):
    ALGORITMOS = [
        ('RSA-1024', 'RSA 1024'),
        ('RSA-2048', 'RSA 2048'),
        ('ElGamal-1024', 'ElGamal 1024'),
        ('DiffieHellman', 'Diffie-Hellman'),
    ]
    TIPOS = [('PUBLICA', 'Pública'), ('PRIVADA', 'Privada')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chaves')
    algoritmo = models.CharField(max_length=20, choices=ALGORITMOS)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    chave_data = models.TextField()
    fingerprint = models.CharField(max_length=64, unique=True)
    parametros_dh = models.TextField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    revogada = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'chaves_criptograficas'

class LogCriptografia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    operacao = models.CharField(max_length=50)
    algoritmo = models.CharField(max_length=50)
    parametros = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'logs_criptografia'