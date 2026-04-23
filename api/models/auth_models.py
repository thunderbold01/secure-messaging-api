from django.db import models
from django.contrib.auth.models import User
import uuid

class Perfil(models.Model):
    """Perfil do usuário"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    telefone = models.CharField(max_length=20, unique=True)
    online = models.BooleanField(default=False)
    ultimo_visto = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'perfis'
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'
    
    def __str__(self):
        return f"{self.usuario.username} - {self.telefone}"