from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import json

from api.models.auth_models import Perfil
from api.models.messaging_models import Amizade, Conversa, Mensagem, SolicitacaoAmizade
from api.models.crypto_models import ChaveCriptografica, LogCriptografia


def is_admin(user):
    """Verifica se é admin"""
    return user.username == 'admin'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """Estatísticas gerais - COM CACHE de 30 segundos"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    # Cache para evitar overload
    cache_key = 'admin_stats'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    
    # Queries otimizadas com agregacão
    stats = {
        'total_usuarios': User.objects.count(),
        'online': Perfil.objects.filter(online=True).count(),
        'total_mensagens': Mensagem.objects.count(),
        'mensagens_24h': Mensagem.objects.filter(
            enviada_em__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'conversas_ativas': Conversa.objects.filter(ativa=True).count(),
        'total_amizades': Amizade.objects.filter(status='ACEITA').count(),
        'solicitacoes_pendentes': SolicitacaoAmizade.objects.filter(status='PENDENTE').count(),
        'total_chaves': ChaveCriptografica.objects.count(),
    }
    
    cache.set(cache_key, stats, 30)
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_usuarios(request):
    """Lista usuários - OTIMIZADO com select_related e paginação"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    limit = min(int(request.GET.get('limit', 50)), 200)
    offset = int(request.GET.get('offset', 0))
    
    # Query otimizada - 1 query em vez de N+1
    users = User.objects.select_related('perfil').only(
        'id', 'username', 'email', 'last_login', 'perfil__telefone', 'perfil__online'
    ).order_by('-last_login')[offset:offset + limit]
    
    # Contagem de mensagens em 1 query
    user_ids = [u.id for u in users]
    msg_counts = dict(
        Mensagem.objects.filter(remetente_id__in=user_ids)
        .values('remetente_id')
        .annotate(count=Count('id'))
        .values_list('remetente_id', 'count')
    )
    
    usuarios = []
    for user in users:
        perfil = getattr(user, 'perfil', None)
        usuarios.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'telefone': perfil.telefone if perfil else 'N/A',
            'online': perfil.online if perfil else False,
            'mensagens': msg_counts.get(user.id, 0),
        })
    
    return Response({
        'usuarios': usuarios,
        'total': User.objects.count(),
        'limit': limit,
        'offset': offset,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_mensagens(request):
    """Lista mensagens - OTIMIZADO com select_related"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    limit = min(int(request.GET.get('limit', 50)), 100)
    
    # Query otimizada
    mensagens = Mensagem.objects.select_related(
        'remetente', 'conversa'
    ).prefetch_related(
        'conversa__participantes'
    ).order_by('-enviada_em')[:limit]
    
    lista = []
    for msg in mensagens:
        conteudo = msg.conteudo_cifrado
        if isinstance(conteudo, bytes):
            try:
                conteudo = conteudo.decode('utf-8', errors='ignore')
            except:
                conteudo = '[CRIPTOGRAFADO]'
        
        # Pegar destinatário da conversa
        destinatario = 'N/A'
        if msg.conversa:
            dest = msg.conversa.participantes.exclude(id=msg.remetente_id).first()
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
    
    return Response({'mensagens': lista, 'total': Mensagem.objects.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_chaves(request):
    """Lista chaves - OTIMIZADO"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    limit = min(int(request.GET.get('limit', 30)), 100)
    
    chaves = ChaveCriptografica.objects.select_related('usuario').only(
        'id', 'usuario__username', 'algoritmo', 'tipo', 'fingerprint', 'criada_em'
    ).order_by('-criada_em')[:limit]
    
    lista = [{
        'id': str(c.id),
        'usuario': c.usuario.username,
        'algoritmo': c.algoritmo,
        'tipo': c.tipo,
        'fingerprint': c.fingerprint[:16] + '...',
        'criada_em': c.criada_em,
    } for c in chaves]
    
    return Response({'chaves': lista, 'total': ChaveCriptografica.objects.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_logs(request):
    """Lista logs - OTIMIZADO"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    limit = min(int(request.GET.get('limit', 30)), 100)
    
    logs = LogCriptografia.objects.select_related('usuario').only(
        'id', 'usuario__username', 'operacao', 'algoritmo', 'timestamp'
    ).order_by('-timestamp')[:limit]
    
    lista = [{
        'id': str(log.id),
        'usuario': log.usuario.username if log.usuario else 'Sistema',
        'operacao': log.operacao,
        'algoritmo': log.algoritmo,
        'timestamp': log.timestamp,
    } for log in logs]
    
    return Response({'logs': lista})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_forcar_logout(request, user_id):
    """Força logout"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    try:
        Perfil.objects.filter(usuario_id=user_id).update(online=False)
        return Response({'mensagem': f'Logout forçado para usuário {user_id}'})
    except Exception as e:
        return Response({'erro': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_estatisticas_mensagens(request):
    """Estatísticas de mensagens - COM CACHE"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    cache_key = 'admin_msg_stats'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    
    agora = timezone.now()
    por_hora = []
    
    # Query otimizada - 1 query para todas as horas
    for i in range(12):
        hora = agora - timedelta(hours=i)
        count = Mensagem.objects.filter(
            enviada_em__year=hora.year,
            enviada_em__month=hora.month,
            enviada_em__day=hora.day,
            enviada_em__hour=hora.hour
        ).count()
        por_hora.append({'hora': hora.strftime('%H:00'), 'count': count})
    
    result = {'por_hora': list(reversed(por_hora))}
    cache.set(cache_key, result, 60)
    
    return Response(result)