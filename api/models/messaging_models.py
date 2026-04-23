from django.db import models
from django.contrib.auth.models import User
import uuid
import json


class SolicitacaoAmizade(models.Model):
    """Solicitação de amizade pendente"""
    
    STATUS = [
        ('PENDENTE', 'Pendente'),
        ('ACEITA', 'Aceita'),
        ('RECUSADA', 'Recusada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    remetente = models.ForeignKey('Perfil', on_delete=models.CASCADE, related_name='solicitacoes_enviadas')
    destinatario = models.ForeignKey('Perfil', on_delete=models.CASCADE, related_name='solicitacoes_recebidas')
    status = models.CharField(max_length=10, choices=STATUS, default='PENDENTE')
    mensagem = models.CharField(max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'solicitacoes_amizade'
        verbose_name = 'Solicitação de Amizade'
        verbose_name_plural = 'Solicitações de Amizade'
        unique_together = ['remetente', 'destinatario']
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.remetente.usuario.username} -> {self.destinatario.usuario.username} ({self.status})"
    
    def aceitar(self):
        """Aceita a solicitação e cria amizade"""
        self.status = 'ACEITA'
        self.save()
        
        # Cria amizade
        from .auth_models import Perfil
        amizade = Amizade.objects.create(
            remetente=self.remetente.usuario,
            destinatario=self.destinatario.usuario,
            status='ACEITA',
            mensagem=self.mensagem,
            aceito_em=self.atualizado_em
        )
        
        return amizade
    
    def recusar(self):
        """Recusa a solicitação"""
        self.status = 'RECUSADA'
        self.save()


class Amizade(models.Model):
    """Relacionamento de amizade com handshake Diffie-Hellman"""
    
    STATUS = [
        ('PENDENTE', 'Pendente'),
        ('ACEITA', 'Aceita'),
        ('RECUSADA', 'Recusada'),
        ('BLOQUEADA', 'Bloqueada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    remetente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='amizades_enviadas')
    destinatario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='amizades_recebidas')
    
    status = models.CharField(max_length=10, choices=STATUS, default='PENDENTE')
    mensagem = models.CharField(max_length=200, blank=True)
    
    # Handshake Diffie-Hellman
    dh_completo = models.BooleanField(default=False)
    dh_parametros_remetente = models.TextField(null=True, blank=True)
    dh_parametros_destinatario = models.TextField(null=True, blank=True)
    segredo_compartilhado = models.BinaryField(null=True, blank=True)
    
    # Canal seguro estabelecido
    canal_seguro = models.BooleanField(default=False)
    algoritmo_canal = models.CharField(max_length=20, default='AES-256-GCM')
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'amizades'
        verbose_name = 'Amizade'
        verbose_name_plural = 'Amizades'
        unique_together = ['remetente', 'destinatario']
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.remetente.username} -> {self.destinatario.username} ({self.status})"
    
    def get_outro_usuario(self, user):
        """Retorna o outro usuário da amizade"""
        if user == self.remetente:
            return self.destinatario
        return self.remetente
    
    def realizar_handshake_dh(self, chave_publica_destinatario: int, chave_privada_remetente: int):
        """Completa o handshake Diffie-Hellman"""
        params_rem = json.loads(self.dh_parametros_remetente)
        
        # Calcula segredo compartilhado
        p = params_rem['p']
        segredo = pow(chave_publica_destinatario, chave_privada_remetente, p)
        
        import hashlib
        self.segredo_compartilhado = hashlib.sha256(str(segredo).encode()).digest()
        self.dh_completo = True
        self.canal_seguro = True
        self.save()
        
        return self.segredo_compartilhado


class Conversa(models.Model):
    """Conversa entre amigos com criptografia ponta-a-ponta"""
    
    TIPOS = [
        ('DIRETA', 'Direta'),
        ('GRUPO', 'Grupo'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='DIRETA')
    
    amizade = models.OneToOneField(
        Amizade, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='conversa'
    )
    
    participantes = models.ManyToManyField(User, related_name='conversas')
    
    algoritmo_padrao = models.CharField(max_length=20, default='HIBRIDO-RSA')
    hash_padrao = models.CharField(max_length=20, default='BLAKE3')
    
    criada_em = models.DateTimeField(auto_now_add=True)
    ultima_mensagem = models.DateTimeField(auto_now=True)
    ativa = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'conversas'
        verbose_name = 'Conversa'
        verbose_name_plural = 'Conversas'
        ordering = ['-ultima_mensagem']
    
    def __str__(self):
        if self.amizade:
            return f"Conversa: {self.amizade}"
        return f"Conversa Grupo {self.id.hex[:8]}"
    
    def get_outro_participante(self, user):
        """Retorna o outro participante da conversa"""
        return self.participantes.exclude(id=user.id).first()
    
    def get_total_mensagens(self):
        """Retorna total de mensagens"""
        return self.mensagens.count()
    
    def get_mensagens_nao_lidas(self, user):
        """Retorna mensagens não lidas para um usuário"""
        return self.mensagens.filter(
            lida_em__isnull=True
        ).exclude(remetente=user).count()


class Mensagem(models.Model):
    """Mensagem com múltiplas camadas de criptografia"""
    
    TIPOS = [
        ('TEXTO', 'Texto'),
        ('IMAGEM', 'Imagem'),
        ('AUDIO', 'Áudio'),
        ('VIDEO', 'Vídeo'),
        ('ARQUIVO', 'Arquivo'),
    ]
    
    ALGORITMOS = [
        ('RSA-1024', 'RSA 1024'),
        ('RSA-2048', 'RSA 2048'),
        ('ElGamal-1024', 'ElGamal 1024'),
        ('HIBRIDO', 'Híbrido (RSA+AES)'),
        ('ECC', 'Curvas Elípticas'),
    ]
    
    HASHES = [
        ('SHA-256', 'SHA-256'),
        ('SHA3-512', 'SHA3-512'),
        ('BLAKE3', 'BLAKE3'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(User, on_delete=models.CASCADE)
    
    tipo = models.CharField(max_length=10, choices=TIPOS, default='TEXTO')
    
    algoritmo = models.CharField(max_length=20, choices=ALGORITMOS)
    conteudo_cifrado = models.BinaryField()
    metadados_cifrados = models.BinaryField(null=True, blank=True)
    
    hash_algoritmo = models.CharField(max_length=10, choices=HASHES)
    hash_original = models.CharField(max_length=128)
    hash_verificado = models.BooleanField(default=False)
    
    assinatura = models.BinaryField(null=True, blank=True)
    assinatura_verificada = models.BooleanField(default=False)
    algoritmo_assinatura = models.CharField(max_length=20, default='RSA-PSS')
    
    nonce = models.BinaryField()
    ephemeral_key = models.BinaryField(null=True, blank=True)
    
    enviada_em = models.DateTimeField(auto_now_add=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'mensagens'
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'
        ordering = ['enviada_em']
        indexes = [
            models.Index(fields=['conversa', 'enviada_em']),
            models.Index(fields=['remetente', 'enviada_em']),
        ]
    
    def __str__(self):
        return f"Mensagem {self.id.hex[:8]} - {self.tipo}"
    
    def marcar_como_entregue(self):
        """Marca mensagem como entregue"""
        from django.utils import timezone
        self.entregue_em = timezone.now()
        self.save(update_fields=['entregue_em'])
    
    def marcar_como_lida(self):
        """Marca mensagem como lida"""
        from django.utils import timezone
        self.lida_em = timezone.now()
        self.save(update_fields=['lida_em'])
    
    def is_expirada(self):
        """Verifica se a mensagem expirou"""
        if self.expira_em:
            from django.utils import timezone
            return timezone.now() > self.expira_em
        return False


class Notificacao(models.Model):
    """Notificações em tempo real"""
    
    TIPOS = [
        ('AMIZADE', 'Solicitação de Amizade'),
        ('AMIZADE_ACEITA', 'Amizade Aceita'),
        ('MENSAGEM', 'Nova Mensagem'),
        ('SISTEMA', 'Sistema'),
        ('CHAMADA', 'Chamada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    
    tipo = models.CharField(max_length=20, choices=TIPOS)
    titulo = models.CharField(max_length=100)
    conteudo = models.TextField()
    
    dados = models.TextField(default='{}')
    
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    
    entregue_websocket = models.BooleanField(default=False)
    entregue_push = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'notificacoes'
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-criada_em']
        indexes = [
            models.Index(fields=['usuario', 'lida']),
            models.Index(fields=['tipo']),
        ]
    
    def __str__(self):
        return f"[{self.tipo}] {self.titulo} - {self.usuario.username}"
    
    def marcar_como_lida(self):
        """Marca notificação como lida"""
        self.lida = True
        self.save(update_fields=['lida'])
    
    def get_dados_json(self):
        """Retorna dados como dicionário"""
        return json.loads(self.dados) if self.dados else {}
    
    @classmethod
    def criar_notificacao_amizade(cls, usuario, remetente, mensagem=None):
        """Cria notificação de solicitação de amizade"""
        return cls.objects.create(
            usuario=usuario,
            tipo='AMIZADE',
            titulo='Nova solicitação de amizade',
            conteudo=f'{remetente.username} quer ser seu amigo',
            dados=json.dumps({
                'remetente_id': remetente.id,
                'remetente_username': remetente.username,
                'mensagem': mensagem
            })
        )
    
    @classmethod
    def criar_notificacao_mensagem(cls, usuario, remetente, conversa_id):
        """Cria notificação de nova mensagem"""
        return cls.objects.create(
            usuario=usuario,
            tipo='MENSAGEM',
            titulo='Nova mensagem',
            conteudo=f'{remetente.username} enviou uma mensagem',
            dados=json.dumps({
                'remetente_id': remetente.id,
                'remetente_username': remetente.username,
                'conversa_id': str(conversa_id)
            })
        )