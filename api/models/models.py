from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    telefone = models.CharField(max_length=20, unique=True)
    nome_completo = models.CharField(max_length=200, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    foto_perfil = models.TextField(blank=True)
    chave_publica = models.TextField(blank=True)
    online = models.BooleanField(default=False)
    ultimo_visto = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.telefone}"

class SolicitacaoAmizade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    remetente = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='solicitacoes_enviadas')
    destinatario = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='solicitacoes_recebidas')
    mensagem = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('PENDENTE', 'Pendente'),
        ('ACEITA', 'Aceita'),
        ('RECUSADA', 'Recusada')
    ], default='PENDENTE')
    criado_em = models.DateTimeField(auto_now_add=True)

class Amizade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    remetente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='amizades_enviadas')
    destinatario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='amizades_recebidas')
    status = models.CharField(max_length=20)
    canal_seguro = models.BooleanField(default=False)
    aceito_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['remetente', 'destinatario']

class Conversa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=20, default='DIRETA')
    participantes = models.ManyToManyField(User, related_name='conversas')
    amizade = models.OneToOneField(Amizade, on_delete=models.CASCADE, null=True, blank=True)
    ultima_mensagem = models.DateTimeField(auto_now=True)
    ativa = models.BooleanField(default=True)

class Mensagem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, default='TEXTO')
    algoritmo = models.CharField(max_length=50, blank=True)
    conteudo_cifrado = models.BinaryField()
    hash_algoritmo = models.CharField(max_length=50, blank=True)
    hash_original = models.CharField(max_length=255, blank=True)
    nonce = models.BinaryField(null=True, blank=True)
    enviada_em = models.DateTimeField(auto_now_add=True)
    lida_em = models.DateTimeField(null=True, blank=True)

class ChaveCriptografica(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chave_cripto')
    chave_publica = models.TextField()
    chave_privada_cifrada = models.TextField()
    algoritmo = models.CharField(max_length=50, default='RSA')
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()

class Notificacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

# NOVOS MODELOS PARA PUSH NOTIFICATIONS
class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField()
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'endpoint')
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"