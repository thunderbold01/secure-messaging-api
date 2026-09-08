from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.http import HttpResponse, FileResponse
from rest_framework.authtoken.views import obtain_auth_token
import os

# Auth Views
from api.views.auth_views import (
    api_root, health_check, registro, login, logout, perfil, crypto_test
)

# Messaging Views
from api.views.messaging_views import (
    buscar_usuario, listar_amigos, listar_solicitacoes, enviar_solicitacao,
    responder_solicitacao, listar_conversas, enviar_mensagem, receber_mensagens,
    listar_notificacoes, info_criptografia, enviar_mensagem_arquivo, baixar_arquivo
)

# Crypto Views
from api.views.crypto_views import (
    crypto_demo, gerar_chaves_rsa, obter_chave_publica,
    verificar_chaves_usuario, revogar_chaves
)

# Admin Views
from api.views.admin_views import (
    admin_stats, admin_usuarios, admin_mensagens, admin_chaves,
    admin_logs, admin_forcar_logout, admin_estatisticas_mensagens, admin_certificados
)

# Notification Views
from api.views.notification_views import (
    save_subscription, remove_subscription, get_notifications, mark_as_read
)

# AI Views
from api.views.ai_views import chat_with_ai, ai_status, ai_clear_history, ai_web_search, ai_web_fetch, ai_web_test


def serve_frontend(request, path=''):
    frontend_dir = getattr(settings, 'FRONTEND_DIR', os.path.join(settings.BASE_DIR, 'frontend'))
    if not path:
        path = 'index.html'
    file_path = os.path.join(frontend_dir, path)
    if os.path.isfile(file_path):
        ext = os.path.splitext(path)[1]
        content_types = {
            '.html': 'text/html',
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.json': 'application/json',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
        }
        ct = content_types.get(ext, 'application/octet-stream')
        return FileResponse(open(file_path, 'rb'), content_type=ct)
    return FileResponse(open(os.path.join(frontend_dir, 'index.html'), 'rb'), content_type='text/html')

urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),
    
    # API Root
    path('api/', api_root, name='api_root'),
    path('api/health/', health_check, name='health_check'),
    
    # Auth
    path('api/registro/', registro, name='registro'),
    path('api/login/', login, name='login'),
    path('api/logout/', logout, name='logout'),
    path('api/perfil/', perfil, name='perfil'),
    path('api/api-token-auth/', obtain_auth_token, name='api_token_auth'),
    path('api/crypto/test/', crypto_test, name='crypto_test'),
    
    # Crypto - RSA e Cifra Híbrida
    path('api/crypto/demo/', crypto_demo, name='crypto_demo'),
    path('api/crypto/gerar-chaves/', gerar_chaves_rsa, name='gerar_chaves_rsa'),
    path('api/crypto/chave-publica/<int:usuario_id>/', obter_chave_publica, name='obter_chave_publica'),
    path('api/crypto/verificar-chaves/', verificar_chaves_usuario, name='verificar_chaves'),
    path('api/crypto/revogar-chaves/', revogar_chaves, name='revogar_chaves'),
    
    # User Management
    path('api/buscar/', buscar_usuario, name='buscar_usuario'),
    path('api/amigos/', listar_amigos, name='listar_amigos'),
    path('api/solicitacoes/', listar_solicitacoes, name='listar_solicitacoes'),
    path('api/solicitacoes/enviar/', enviar_solicitacao, name='enviar_solicitacao'),
    path('api/solicitacoes/<uuid:solicitacao_id>/responder/', responder_solicitacao, name='responder_solicitacao'),
    
    # Messaging
    path('api/conversas/', listar_conversas, name='listar_conversas'),
    path('api/conversas/<uuid:conversa_id>/enviar/', enviar_mensagem, name='enviar_mensagem'),
    path('api/conversas/<uuid:conversa_id>/mensagens/', receber_mensagens, name='receber_mensagens'),
    path('api/conversas/<uuid:conversa_id>/enviar-arquivo/', enviar_mensagem_arquivo, name='enviar_arquivo'),
    path('api/mensagens/<uuid:mensagem_id>/baixar-arquivo/', baixar_arquivo, name='baixar_arquivo'),
    
    # Notifications
    path('api/notificacoes/', listar_notificacoes, name='listar_notificacoes'),
    path('api/info/criptografia/', info_criptografia, name='info_criptografia'),
    
    # Push Notifications
    path('api/push/save-subscription/', save_subscription, name='save_subscription'),
    path('api/push/remove-subscription/', remove_subscription, name='remove_subscription'),
    path('api/push/notifications/', get_notifications, name='get_notifications'),
    path('api/push/notifications/<uuid:notification_id>/read/', mark_as_read, name='mark_as_read'),
    
    # AI Chat
    path('api/ai/chat/', chat_with_ai, name='chat_with_ai'),
    path('api/ai/status/', ai_status, name='ai_status'),
    path('api/ai/clear/', ai_clear_history, name='ai_clear_history'),
    path('api/ai/web-search/', ai_web_search, name='ai_web_search'),
    path('api/ai/web-fetch/', ai_web_fetch, name='ai_web_fetch'),
    path('api/ai/web-test/', ai_web_test, name='ai_web_test'),
    
    # Admin
    path('api/admin/stats/', admin_stats, name='admin_stats'),
    path('api/admin/usuarios/', admin_usuarios, name='admin_usuarios'),
    path('api/admin/mensagens/', admin_mensagens, name='admin_mensagens'),
    path('api/admin/chaves/', admin_chaves, name='admin_chaves'),
    path('api/admin/logs/', admin_logs, name='admin_logs'),
    path('api/admin/estatisticas/', admin_estatisticas_mensagens, name='admin_estatisticas'),
    path('api/admin/forcar-logout/<int:user_id>/', admin_forcar_logout, name='admin_forcar_logout'),
    path('api/admin/certificados/', admin_certificados, name='admin_certificados'),
]