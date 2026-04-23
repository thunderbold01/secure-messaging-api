from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import json

# Modelos simples para push notifications (sem depender de bibliotecas externas)
from django.db import models
from django.contrib.auth.models import User
import uuid

class PushSubscription(models.Model):
    """Armazena inscrições de push notification"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField()
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'push_subscriptions'
        unique_together = ['user', 'endpoint']

class Notification(models.Model):
    """Notificações push enviadas"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_notifications')
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'push_notifications'
        ordering = ['-created_at']


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_subscription(request):
    """Salvar subscription do usuário para push notifications"""
    try:
        data = json.loads(request.body)
        
        subscription, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=data['endpoint'],
            defaults={
                'p256dh': data['keys']['p256dh'],
                'auth': data['keys']['auth']
            }
        )
        
        return Response({'status': 'subscription saved'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_subscription(request):
    """Remover subscription do usuário"""
    try:
        data = json.loads(request.body)
        PushSubscription.objects.filter(
            user=request.user,
            endpoint=data.get('endpoint', '')
        ).delete()
        
        return Response({'status': 'subscription removed'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Listar notificações do usuário"""
    notifications = Notification.objects.filter(user=request.user, is_read=False)[:20]
    data = [{
        'id': str(n.id),
        'type': n.type,
        'title': n.title,
        'body': n.body,
        'data': n.data,
        'created_at': n.created_at.isoformat()
    } for n in notifications]
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    """Marcar notificação como lida"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)


# Função auxiliar para enviar notificações (usada pelo messaging_views)
def enviar_notificacao_push(usuario, titulo, conteudo, tipo='message', dados_extra=None):
    """Enviar notificação push para um usuário"""
    try:
        # Salvar no banco de dados
        Notification.objects.create(
            user=usuario,
            type=tipo,
            title=titulo,
            body=conteudo,
            data=dados_extra or {}
        )
        
        # Nota: O envio real de push notification depende do Service Worker no frontend
        # O backend apenas armazena a notificação. O frontend faz polling ou recebe via SW.
        
        print(f"📩 Notificação criada para {usuario.username}: {titulo}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar notificação: {e}")
        return False