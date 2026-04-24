from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json
import uuid

# Importar modelos do lugar correto
from api.models.notification_models import PushSubscription, Notification


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
        Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
        return Response({'status': 'marked as read'})
    except Exception:
        return Response({'status': 'ok'})


def enviar_notificacao_push(usuario, titulo, conteudo, tipo='message', dados_extra=None):
    """Enviar notificação push para um usuário"""
    try:
        # Aceitar tanto objeto User quanto user_id
        user_obj = usuario if hasattr(usuario, 'id') else None
        user_id = usuario if isinstance(usuario, (int, str)) else usuario.id
        
        Notification.objects.create(
            user_id=user_id,
            type=tipo,
            title=titulo,
            body=conteudo,
            data=dados_extra or {}
        )
        
        username = user_obj.username if user_obj else f'User_{user_id}'
        print(f"📩 Notificação criada para {username}: {titulo}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar notificação: {e}")
        return False