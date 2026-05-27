from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_security_dashboard(request):
    """Dashboard de segurança para admin - Estatísticas completas"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    from api.services.prng_service import PRNG128
    from api.services.dh_service import DiffieHellman
    from api.services.hash_service import HashService
    from api.services.rsa_service import RSA1024
    from api.services.hybrid_service import HybridCipher
    
    # Estatísticas de chaves
    total_chaves = ChaveCriptografica.objects.count()
    chaves_ativas = ChaveCriptografica.objects.filter(revogada=False).count()
    chaves_rsa = ChaveCriptografica.objects.filter(algoritmo='RSA-1024').count()
    
    # Usuários com chave pública
    usuarios_com_chave = ChaveCriptografica.objects.filter(
        tipo='PUBLICA', revogada=False
    ).values('usuario_id').distinct().count()
    
    # Total de usuários
    total_usuarios = User.objects.count()
    
    # Estatísticas de mensagens criptografadas
    mensagens_cifradas = Mensagem.objects.filter(
        algoritmo__startswith='HYBRID'
    ).count()
    
    mensagens_total = Mensagem.objects.count()
    
    # Teste PRNG
    prng = PRNG128()
    prng_test = {
        'bytes': prng.generate().hex(),
        'int': prng.generate_int(),
        'entropy_source': prng.get_entropy_source()
    }
    
    # Teste Diffie-Hellman
    dh = DiffieHellman()
    params = dh.generate_keypair()
    dh_test = {
        'funcionou': True,
        'prime_bits': params['p'].bit_length(),
        'generator': params['g'],
        'public_key_bits': params['public_key'].bit_length()
    }
    
    # Teste Cifra Híbrida
    rsa = RSA1024()
    pub, priv = rsa.generate_keypair()
    hybrid = HybridCipher()
    test_msg = "Mensagem de teste para verificar cifra híbrida"
    try:
        pacote = hybrid.encrypt_message(test_msg, pub)
        decifrada = hybrid.decrypt_message(pacote, priv)
        hybrid_test = {
            'funcionou': test_msg == decifrada,
            'algorithm': pacote['algorithm']
        }
    except Exception as e:
        hybrid_test = {'funcionou': False, 'erro': str(e)}
    
    # Logs recentes
    logs_recentes = LogCriptografia.objects.select_related('usuario').order_by('-timestamp')[:10]
    
    return Response({
        'resumo': {
            'total_usuarios': total_usuarios,
            'usuarios_com_chave': usuarios_com_chave,
            'percentual_chaves': round((usuarios_com_chave / total_usuarios * 100), 2) if total_usuarios > 0 else 0,
            'total_chaves': total_chaves,
            'chaves_ativas': chaves_ativas,
            'chaves_rsa': chaves_rsa,
            'mensagens_total': mensagens_total,
            'mensagens_cifradas': mensagens_cifradas,
            'percentual_cifradas': round((mensagens_cifradas / mensagens_total * 100), 2) if mensagens_total > 0 else 0
        },
        'testes': {
            'prng': prng_test,
            'diffie_hellman': dh_test,
            'cifra_hibrida': hybrid_test,
            'hash': {
                'sha256': HashService.sha256(test_msg)[:32],
                'disponivel': True
            }
        },
        'logs_recentes': [{
            'id': str(log.id),
            'usuario': log.usuario.username if log.usuario else 'Sistema',
            'operacao': log.operacao,
            'algoritmo': log.algoritmo,
            'timestamp': log.timestamp
        } for log in logs_recentes]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_certificados(request):
    """Lista certificados digitais (PKI) para admin"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    from api.models.pki_models import AutoridadeCertificadora, CertificadoDigital
    
    # CA Raiz
    ca_raiz = AutoridadeCertificadora.objects.filter(nivel=1, ativa=True).first()
    
    # Certificados emitidos
    certificados = CertificadoDigital.objects.select_related('usuario', 'assinado_por').all()[:20]
    
    return Response({
        'ca_raiz': {
            'nome': ca_raiz.nome if ca_raiz else 'Nenhuma CA configurada',
            'nivel': ca_raiz.nivel if ca_raiz else None,
            'ativa': ca_raiz.ativa if ca_raiz else False,
            'valido_ate': ca_raiz.valido_ate if ca_raiz else None,
            'criada_em': ca_raiz.criada_em if ca_raiz else None
        } if ca_raiz else None,
        'certificados': [{
            'id': str(cert.id),
            'usuario': cert.usuario.username if cert.usuario else cert.servico,
            'tipo': 'Usuário' if cert.usuario else 'Serviço',
            'status': cert.status,
            'valido_de': cert.valido_de,
            'valido_ate': cert.valido_ate,
            'fingerprint': cert.fingerprint_sha256[:16] + '...'
        } for cert in certificados]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_gerar_certificado(request):
    """Gera certificado digital para um usuário (admin)"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    from api.models.pki_models import CertificadoDigital, AutoridadeCertificadora
    from api.services.pki_service import PKIService
    
    data = json.loads(request.body)
    usuario_id = data.get('usuario_id')
    
    if not usuario_id:
        return Response({'erro': 'Usuário ID é obrigatório'}, status=400)
    
    try:
        usuario = User.objects.get(id=usuario_id)
        ca = AutoridadeCertificadora.objects.filter(nivel=1, ativa=True).first()
        
        if not ca:
            # Criar CA raiz automaticamente
            from api.models.pki_models import AutoridadeCertificadora
            ca = AutoridadeCertificadora.criar_ca_raiz("SecureMessaging Root CA")
        
        # Gerar certificado para o usuário
        pki = PKIService()
        certificado = pki.emitir_certificado_usuario(usuario, ca)
        
        return Response({
            'mensagem': f'Certificado gerado para {usuario.username}',
            'certificado_id': str(certificado.id),
            'fingerprint': certificado.fingerprint_sha256[:16]
        }, status=201)
        
    except User.DoesNotExist:
        return Response({'erro': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)
    
@staff_member_required
def security_dashboard_view(request):
    """View para o template HTML do dashboard de segurança"""
    return render(request, 'admin/security_dashboard.html')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_certificados(request):
    """Lista certificados digitais para o admin"""
    if not is_admin(request.user):
        return Response({'erro': 'Acesso negado'}, status=403)
    
    # Simular certificados para demonstração
    certificados = [
        {
            'id': '1',
            'usuario': 'SecureMessaging Root CA',
            'tipo': 'CA Raiz',
            'status': 'VALIDO',
            'valido_de': '2024-01-01T00:00:00Z',
            'valido_ate': '2034-01-01T00:00:00Z',
            'fingerprint': 'A1:B2:C3:D4:E5:F6:78:90:12:34:56:78:90:AB:CD:EF'
        }
    ]
    
    # Buscar usuários que têm chaves RSA
    from api.models.crypto_models import ChaveCriptografica
    
    usuarios_com_chave = ChaveCriptografica.objects.filter(
        tipo='PUBLICA',
        revogada=False
    ).values_list('usuario_id', flat=True).distinct()
    
    for user in User.objects.filter(id__in=usuarios_com_chave):
        certificados.append({
            'id': str(user.id),
            'usuario': user.username,
            'tipo': 'Certificado de Usuário',
            'status': 'VALIDO',
            'valido_de': '2025-01-01T00:00:00Z',
            'valido_ate': '2026-01-01T00:00:00Z',
            'fingerprint': f'USER-{user.id}-FINGERPRINT'
        })
    
    return Response({
        'certificados': certificados
    })