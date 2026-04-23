from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import json

from api.models.auth_models import Perfil
from api.models.messaging_models import Amizade, Conversa, Mensagem, SolicitacaoAmizade
from api.models.crypto_models import ChaveCriptografica, LogCriptografia

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """Estatísticas gerais para o admin"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    total_usuarios = User.objects.count()
    online = Perfil.objects.filter(online=True).count()
    total_mensagens = Mensagem.objects.count()
    mensagens_24h = Mensagem.objects.filter(enviada_em__gte=timezone.now() - timedelta(hours=24)).count()
    conversas_ativas = Conversa.objects.filter(ativa=True).count()
    total_amizades = Amizade.objects.filter(status='ACEITA').count()
    solicitacoes_pendentes = SolicitacaoAmizade.objects.filter(status='PENDENTE').count()
    total_chaves = ChaveCriptografica.objects.count()
    
    return Response({
        'total_usuarios': total_usuarios,
        'online': online,
        'total_mensagens': total_mensagens,
        'mensagens_24h': mensagens_24h,
        'conversas_ativas': conversas_ativas,
        'total_amizades': total_amizades,
        'solicitacoes_pendentes': solicitacoes_pendentes,
        'total_chaves': total_chaves,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_usuarios(request):
    """Lista todos os usuários (apenas admin)"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    usuarios = []
    for user in User.objects.all().order_by('-last_login'):
        try:
            perfil = Perfil.objects.get(usuario=user)
            telefone = perfil.telefone
            online = perfil.online
        except Perfil.DoesNotExist:
            telefone = 'N/A'
            online = False
        
        mensagens_count = Mensagem.objects.filter(remetente=user).count()
        
        usuarios.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'telefone': telefone,
            'online': online,
            'mensagens': mensagens_count,
        })
    
    return Response({'usuarios': usuarios})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_mensagens(request):
    """Lista todas as mensagens (apenas admin)"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    mensagens = Mensagem.objects.all().order_by('-enviada_em')[:50]
    
    lista = []
    for msg in mensagens:
        conteudo = msg.conteudo_cifrado
        if isinstance(conteudo, bytes):
            try:
                conteudo = conteudo.decode('utf-8')
            except:
                conteudo = '[DADOS CRIPTOGRAFADOS]'
        
        destinatario = 'N/A'
        if msg.conversa:
            dest = msg.conversa.participantes.exclude(id=msg.remetente.id).first()
            if dest:
                destinatario = dest.username
        
        lista.append({
            'id': str(msg.id),
            'remetente': msg.remetente.username,
            'destinatario': destinatario,
            'conteudo': str(conteudo)[:100],
            'algoritmo': msg.algoritmo,
            'enviada_em': msg.enviada_em,
        })
    
    return Response({'mensagens': lista})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_chaves(request):
    """Lista todas as chaves criptográficas (apenas admin)"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    chaves = ChaveCriptografica.objects.all().order_by('-criada_em')[:30]
    
    lista = []
    for chave in chaves:
        lista.append({
            'id': str(chave.id),
            'usuario': chave.usuario.username,
            'algoritmo': chave.algoritmo,
            'tipo': chave.tipo,
            'fingerprint': chave.fingerprint[:16] + '...',
            'criada_em': chave.criada_em,
        })
    
    return Response({'chaves': lista})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_logs(request):
    """Lista logs de criptografia (apenas admin)"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    logs = LogCriptografia.objects.all().order_by('-timestamp')[:30]
    
    lista = []
    for log in logs:
        lista.append({
            'id': str(log.id),
            'usuario': log.usuario.username if log.usuario else 'Sistema',
            'operacao': log.operacao,
            'algoritmo': log.algoritmo,
            'timestamp': log.timestamp,
        })
    
    return Response({'logs': lista})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_forcar_logout(request, user_id):
    """Força logout de um usuário"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    try:
        user = User.objects.get(id=user_id)
        perfil = Perfil.objects.get(usuario=user)
        perfil.online = False
        perfil.save()
        
        return Response({'mensagem': f'Logout forçado para {user.username}'})
    except User.DoesNotExist:
        return Response({'erro': 'Usuário não encontrado'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_estatisticas_mensagens(request):
    """Estatísticas de mensagens por hora"""
    
    if request.user.username != 'admin':
        return Response({'erro': 'Acesso negado'}, status=403)
    
    agora = timezone.now()
    por_hora = []
    for i in range(12):
        hora = agora - timedelta(hours=i)
        count = Mensagem.objects.filter(
            enviada_em__year=hora.year,
            enviada_em__month=hora.month,
            enviada_em__day=hora.day,
            enviada_em__hour=hora.hour
        ).count()
        por_hora.append({
            'hora': hora.strftime('%H:00'),
            'count': count
        })
    
    return Response({'por_hora': list(reversed(por_hora))})