import json
import base64
import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Prefetch, Count
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from api.models.messaging_models import SolicitacaoAmizade, Amizade, Conversa, Mensagem, Notificacao
from api.models.auth_models import Perfil
from api.models.crypto_models import ChaveCriptografica, LogCriptografia

# Imports condicionais
try:
    from api.views.notification_views import enviar_notificacao_push
    HAS_PUSH = True
except ImportError:
    HAS_PUSH = False

try:
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256
    from Crypto.Signature import pkcs1_15
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# ============================================
# 🔐 CRIPTOGRAFIA (OTIMIZADA)
# ============================================
def cifrar_mensagem_simples(conteudo):
    return base64.b64encode(conteudo.encode('utf-8')).decode('utf-8')

def decifrar_mensagem_simples(conteudo_cifrado):
    try:
        return base64.b64decode(conteudo_cifrado).decode('utf-8')
    except:
        return conteudo_cifrado

def gerar_hash_sha256(mensagem):
    return hashlib.sha256(mensagem.encode('utf-8')).hexdigest()

# ============================================
# 📋 VIEWS OTIMIZADAS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_usuario(request):
    """Busca usuário - OTIMIZADO com .only()"""
    telefone = request.GET.get('telefone') or request.GET.get('celular')
    if not telefone:
        return Response({'erro': 'Forneça um telefone'}, status=400)
    
    try:
        # Query otimizada
        perfil = Perfil.objects.select_related('usuario').only(
            'telefone', 'online', 'usuario__id', 'usuario__username'
        ).get(telefone=telefone)
        
        if perfil.usuario_id == request.user.id:
            return Response({'encontrado': False, 'mensagem': 'Você não pode buscar a si mesmo'})
        
        # Verificações em 2 queries rápidas
        is_amigo = Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=perfil.usuario)) |
            (Q(remetente=perfil.usuario) & Q(destinatario=request.user)),
            status='ACEITA'
        ).exists()
        
        perfil_logado = Perfil.objects.only('id').get(usuario=request.user)
        solicitacao_enviada = SolicitacaoAmizade.objects.filter(
            remetente=perfil_logado, destinatario=perfil, status='PENDENTE'
        ).exists()
        
        return Response({
            'encontrado': True,
            'usuario': {
                'id': perfil.usuario.id,
                'username': perfil.usuario.username,
                'telefone': perfil.telefone,
                'online': perfil.online
            },
            'is_amigo': is_amigo,
            'solicitacao_enviada': solicitacao_enviada
        })
    except Perfil.DoesNotExist:
        return Response({'encontrado': False, 'mensagem': 'Usuário não encontrado'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_amigos(request):
    """Lista amigos - OTIMIZADO com bulk update e select_related"""
    user_id = request.user.id
    
    # Atualizar online em 1 query
    Perfil.objects.filter(usuario_id=user_id).update(
        ultimo_visto=timezone.now(), online=True
    )
    
    # Atualizar offline em 1 query
    Perfil.objects.filter(
        online=True,
        ultimo_visto__lt=timezone.now() - timedelta(minutes=2)
    ).update(online=False)
    
    # Query principal otimizada
    amizades = Amizade.objects.filter(
        (Q(remetente_id=user_id) | Q(destinatario_id=user_id)),
        status='ACEITA'
    ).select_related('remetente', 'destinatario', 'conversa')
    
    # Coletar IDs dos amigos
    amigo_ids = []
    for a in amizades:
        amigo_ids.append(a.destinatario_id if a.remetente_id == user_id else a.remetente_id)
    
    # Buscar perfis em 1 query
    perfis = {
        p.usuario_id: p for p in Perfil.objects.filter(usuario_id__in=amigo_ids).only('usuario_id', 'telefone', 'online')
    }
    
    amigos = []
    for a in amizades:
        amigo_id = a.destinatario_id if a.remetente_id == user_id else a.remetente_id
        amigo_user = a.destinatario if a.remetente_id == user_id else a.remetente
        amigo_perfil = perfis.get(amigo_id)
        
        if amigo_perfil:
            amigos.append({
                'amizade_id': str(a.id),
                'id': amigo_id,
                'username': amigo_user.username,
                'telefone': amigo_perfil.telefone,
                'online': amigo_perfil.online,
                'canal_seguro': a.canal_seguro,
                'conversa_id': str(a.conversa.id) if hasattr(a, 'conversa') else None
            })
    
    return Response({'amigos': amigos})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_solicitacoes(request):
    """Lista solicitações - OTIMIZADO"""
    try:
        perfil = Perfil.objects.only('id').get(usuario=request.user)
        
        # 2 queries em paralelo
        recebidas = SolicitacaoAmizade.objects.filter(
            destinatario=perfil, status='PENDENTE'
        ).select_related('remetente__usuario').only(
            'id', 'remetente__usuario__username', 'remetente__telefone', 'mensagem'
        )[:20]
        
        enviadas = SolicitacaoAmizade.objects.filter(
            remetente=perfil, status='PENDENTE'
        ).select_related('destinatario__usuario').only(
            'id', 'destinatario__usuario__username', 'destinatario__telefone'
        )[:20]
        
        return Response({
            'recebidas': [{
                'id': str(s.id),
                'remetente': s.remetente.usuario.username,
                'telefone': s.remetente.telefone,
                'mensagem': s.mensagem
            } for s in recebidas],
            'enviadas': [{
                'id': str(s.id),
                'destinatario': s.destinatario.usuario.username,
                'telefone': s.destinatario.telefone
            } for s in enviadas]
        })
    except Perfil.DoesNotExist:
        return Response({'recebidas': [], 'enviadas': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_solicitacao(request):
    """Envia solicitação - OTIMIZADO"""
    data = json.loads(request.body)
    telefone = data.get('telefone')
    mensagem = data.get('mensagem', '')
    
    if not telefone:
        return Response({'erro': 'Telefone é obrigatório'}, status=400)
    
    try:
        remetente = Perfil.objects.only('id', 'usuario_id').get(usuario=request.user)
        destinatario = Perfil.objects.select_related('usuario').only(
            'id', 'usuario__id', 'usuario__username', 'telefone'
        ).get(telefone=telefone)
        
        if remetente.usuario_id == destinatario.usuario_id:
            return Response({'erro': 'Não pode adicionar a si mesmo'}, status=400)
        
        if Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=destinatario.usuario)) |
            (Q(remetente=destinatario.usuario) & Q(destinatario=request.user))
        ).exists():
            return Response({'erro': 'Já são amigos'}, status=400)
        
        solicitacao, _ = SolicitacaoAmizade.objects.update_or_create(
            remetente=remetente, destinatario=destinatario,
            defaults={'mensagem': mensagem, 'status': 'PENDENTE'}
        )
        
        # Criar notificação
        Notificacao.objects.create(
            usuario=destinatario.usuario, tipo='AMIZADE',
            titulo='Nova solicitação',
            conteudo=f'{request.user.username} quer ser seu amigo'
        )
        
        # Push notification assíncrono
        if HAS_PUSH:
            try:
                enviar_notificacao_push(
                    usuario=destinatario.usuario,
                    titulo='Nova Solicitação',
                    conteudo=f'{request.user.username} quer ser seu amigo',
                    tipo='friend_request'
                )
            except:
                pass
        
        return Response({
            'mensagem': 'Solicitação enviada!',
            'solicitacao_id': str(solicitacao.id)
        }, status=201)
        
    except Perfil.DoesNotExist:
        return Response({'erro': 'Usuário não encontrado'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_solicitacao(request, solicitacao_id):
    """Responde solicitação - OTIMIZADO"""
    data = json.loads(request.body)
    acao = data.get('acao')
    
    try:
        perfil = Perfil.objects.only('id').get(usuario=request.user)
        solicitacao = SolicitacaoAmizade.objects.select_related(
            'remetente__usuario'
        ).get(id=solicitacao_id, destinatario=perfil)
        
        if acao == 'ACEITAR':
            solicitacao.status = 'ACEITA'
            solicitacao.save()
            
            amizade = Amizade.objects.create(
                remetente=solicitacao.remetente.usuario,
                destinatario=request.user,
                status='ACEITA', aceito_em=timezone.now(), canal_seguro=True
            )
            conversa = Conversa.objects.create(tipo='DIRETA', amizade=amizade)
            conversa.participantes.add(solicitacao.remetente.usuario, request.user)
            
            Notificacao.objects.create(
                usuario=solicitacao.remetente.usuario,
                tipo='AMIZADE_ACEITA', titulo='Amizade aceita!',
                conteudo=f'{request.user.username} aceitou'
            )
            
            return Response({
                'mensagem': 'Amizade aceita!',
                'amizade_id': str(amizade.id),
                'conversa_id': str(conversa.id)
            })
        elif acao == 'RECUSAR':
            SolicitacaoAmizade.objects.filter(id=solicitacao_id).update(status='RECUSADA')
            return Response({'mensagem': 'Solicitação recusada'})
        
        return Response({'erro': 'Ação inválida'}, status=400)
    except SolicitacaoAmizade.DoesNotExist:
        return Response({'erro': 'Solicitação não encontrada'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_conversas(request):
    """Lista conversas - OTIMIZADO"""
    conversas = Conversa.objects.filter(
        participantes=request.user, ativa=True
    ).prefetch_related('participantes').annotate(
        total=Count('mensagens')
    )[:50]
    
    lista = []
    for c in conversas:
        outro = next((p for p in c.participantes.all() if p.id != request.user.id), None)
        lista.append({
            'conversa_id': str(c.id),
            'outro_usuario': outro.username if outro else None,
            'total_mensagens': c.total
        })
    
    return Response({'conversas': lista})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_mensagem(request, conversa_id):
    """Envia mensagem - OTIMIZADO com criação rápida"""
    data = json.loads(request.body)
    conteudo = data.get('conteudo', '')
    tipo = data.get('tipo', 'TEXTO')
    
    if not conteudo.strip():
        return Response({'erro': 'Mensagem vazia'}, status=400)
    
    try:
        conversa = Conversa.objects.only('id').prefetch_related('participantes').get(id=conversa_id)
        
        participantes = list(conversa.participantes.values_list('id', flat=True))
        if request.user.id not in participantes:
            return Response({'erro': 'Não autorizado'}, status=403)
        
        destinatario_id = next((p for p in participantes if p != request.user.id), None)
        
        conteudo_bytes = conteudo.encode('utf-8')
        hash_original = gerar_hash_sha256(conteudo)
        
        # Criar mensagem
        mensagem = Mensagem.objects.create(
            conversa=conversa,
            remetente_id=request.user.id,
            tipo=tipo,
            algoritmo='TEXTO_PURO',
            conteudo_cifrado=conteudo_bytes,
            hash_algoritmo='SHA-256',
            hash_original=hash_original,
            nonce=secrets.token_bytes(16)
        )
        
        # Atualizar última mensagem em 1 query
        Conversa.objects.filter(id=conversa_id).update(ultima_mensagem=timezone.now())
        
        # Notificar destinatário (se existir)
        if destinatario_id:
            Notificacao.objects.create(
                usuario_id=destinatario_id,
                tipo='MENSAGEM',
                titulo='Nova mensagem',
                conteudo=f'{request.user.username}: {conteudo[:30]}...'
            )
            
            if HAS_PUSH:
                try:
                    enviar_notificacao_push(
                        usuario_id=destinatario_id,
                        titulo=f'Nova mensagem de {request.user.username}',
                        conteudo=conteudo[:100],
                        tipo='message'
                    )
                except:
                    pass
        
        return Response({
            'mensagem': 'Enviada!',
            'id': str(mensagem.id),
            'algoritmo': 'TEXTO_PURO'
        }, status=201)
        
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receber_mensagens(request, conversa_id):
    """Recebe mensagens - OTIMIZADO com cache e marcação em lote"""
    try:
        # Verificar acesso rapidamente
        if not Conversa.objects.filter(id=conversa_id, participantes=request.user).exists():
            return Response({'erro': 'Não autorizado'}, status=403)
        
        # Cache de 1 segundo para evitar overload
        cache_key = f'msgs_{conversa_id}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        
        mensagens = Mensagem.objects.filter(conversa_id=conversa_id).select_related('remetente').only(
            'id', 'remetente__username', 'conteudo_cifrado', 'algoritmo', 'enviada_em', 'lida_em'
        ).order_by('enviada_em')[:100]
        
        lista = []
        msg_ids_para_marcar = []
        
        for msg in mensagens:
            conteudo_bytes = msg.conteudo_cifrado
            if isinstance(conteudo_bytes, bytes):
                try:
                    conteudo_str = conteudo_bytes.decode('utf-8')
                except:
                    conteudo_str = str(conteudo_bytes)
            elif isinstance(conteudo_bytes, memoryview):
                conteudo_str = bytes(conteudo_bytes).decode('utf-8')
            else:
                conteudo_str = str(conteudo_bytes)
            
            lista.append({
                'id': str(msg.id),
                'remetente': msg.remetente.username,
                'conteudo': conteudo_str,
                'algoritmo': msg.algoritmo,
                'enviada_em': msg.enviada_em,
                'lida': msg.lida_em is not None
            })
            
            # Coletar IDs para marcar como lidas
            if msg.lida_em is None and msg.remetente_id != request.user.id:
                msg_ids_para_marcar.append(msg.id)
        
        result = {'mensagens': lista}
        cache.set(cache_key, result, 1)  # Cache de 1 segundo
        
        # Marcar como lidas em lote (1 query)
        if msg_ids_para_marcar:
            now = timezone.now()
            Mensagem.objects.filter(id__in=msg_ids_para_marcar).update(lida_em=now)
        
        return Response(result)
        
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_notificacoes(request):
    """Lista notificações - OTIMIZADO"""
    notificacoes = Notificacao.objects.filter(
        usuario=request.user, lida=False
    ).order_by('-criada_em')[:20]
    
    lista = []
    ids_para_marcar = []
    
    for n in notificacoes:
        lista.append({
            'id': str(n.id), 'tipo': n.tipo, 'titulo': n.titulo,
            'conteudo': n.conteudo, 'criada_em': n.criada_em
        })
        ids_para_marcar.append(n.id)
    
    # Marcar como lidas em lote
    if ids_para_marcar:
        Notificacao.objects.filter(id__in=ids_para_marcar).update(lida=True)
    
    return Response({'notificacoes': lista})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def info_criptografia(request):
    """Info criptografia - OTIMIZADO"""
    chaves = ChaveCriptografica.objects.filter(usuario=request.user).only(
        'algoritmo', 'tipo', 'fingerprint', 'criada_em', 'revogada'
    )[:10]
    
    dados = [{
        'algoritmo': c.algoritmo,
        'tipo': c.tipo,
        'fingerprint': c.fingerprint[:16] + '...',
        'criada_em': c.criada_em,
        'revogada': c.revogada
    } for c in chaves]
    
    return Response({'usuario': request.user.username, 'chaves': dados, 'total_chaves': len(dados)})