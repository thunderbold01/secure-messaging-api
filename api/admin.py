from django.contrib import admin
from api.models.auth_models import Perfil
from api.models.messaging_models import SolicitacaoAmizade, Amizade, Conversa, Mensagem
from api.models.crypto_models import ChaveCriptografica, LogCriptografia

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'telefone', 'online', 'ultimo_visto']
    search_fields = ['usuario__username', 'telefone']

@admin.register(Amizade)
class AmizadeAdmin(admin.ModelAdmin):
    list_display = ['remetente', 'destinatario', 'status', 'canal_seguro', 'criado_em']
    list_filter = ['status', 'canal_seguro']

@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ['id_curto', 'remetente', 'tipo', 'algoritmo', 'hash_verificado', 'enviada_em']
    list_filter = ['tipo', 'algoritmo', 'hash_algoritmo']
    readonly_fields = ['id', 'enviada_em']
    
    def id_curto(self, obj):
        return str(obj.id)[:8]

@admin.register(ChaveCriptografica)
class ChaveCriptograficaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'algoritmo', 'tipo', 'revogada', 'criada_em']
    list_filter = ['algoritmo', 'tipo']

@admin.register(LogCriptografia)
class LogCriptografiaAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'usuario', 'operacao', 'algoritmo']
    list_filter = ['operacao', 'algoritmo']
    readonly_fields = ['id', 'timestamp']

admin.site.register(SolicitacaoAmizade)
admin.site.register(Conversa)