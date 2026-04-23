from django.urls import path
from api.views import auth_views, crypto_views, messaging_views, admin_views

urlpatterns = [
    path('', auth_views.api_root, name='api-root'),
    
    # Autenticação
    path('registro/', auth_views.registro, name='registro'),
    path('login/', auth_views.login, name='login'),
    path('logout/', auth_views.logout, name='logout'),
    path('perfil/', auth_views.perfil, name='perfil'),
    
    # Criptografia
    path('crypto/demo/', crypto_views.crypto_demo, name='crypto-demo'),
    
    # Usuários e Amizade
    path('buscar/', messaging_views.buscar_usuario, name='buscar'),
    path('amigos/', messaging_views.listar_amigos, name='amigos'),
    path('solicitacoes/', messaging_views.listar_solicitacoes, name='solicitacoes'),
    path('solicitacoes/enviar/', messaging_views.enviar_solicitacao, name='enviar-solicitacao'),
    path('solicitacoes/<uuid:solicitacao_id>/responder/', messaging_views.responder_solicitacao, name='responder-solicitacao'),
    
    # Conversas e Mensagens
    path('conversas/', messaging_views.listar_conversas, name='listar-conversas'),
    path('conversas/<uuid:conversa_id>/enviar/', messaging_views.enviar_mensagem, name='enviar-mensagem'),
    path('conversas/<uuid:conversa_id>/mensagens/', messaging_views.receber_mensagens, name='receber-mensagens'),
    
    # Notificações
    path('notificacoes/', messaging_views.listar_notificacoes, name='notificacoes'),
    
    # ========== ROTAS ADMIN ==========
    path('admin/stats/', admin_views.admin_stats, name='admin-stats'),
    path('admin/usuarios/', admin_views.admin_usuarios, name='admin-usuarios'),
    path('admin/mensagens/', admin_views.admin_mensagens, name='admin-mensagens'),
    path('admin/chaves/', admin_views.admin_chaves, name='admin-chaves'),
    path('admin/logs/', admin_views.admin_logs, name='admin-logs'),
    path('admin/estatisticas/', admin_views.admin_estatisticas_mensagens, name='admin-estatisticas'),
    path('admin/forcar-logout/<int:user_id>/', admin_views.admin_forcar_logout, name='admin-forcar-logout'),
]