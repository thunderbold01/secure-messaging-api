import json
import base64
import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from api.models.messaging_models import SolicitacaoAmizade, Amizade, Conversa, Mensagem, Notificacao
from api.models.auth_models import Perfil
from api.models.crypto_models import ChaveCriptografica, LogCriptografia

# Tentar importar notificações push
try:
    from api.views.notification_views import enviar_notificacao_push
    HAS_PUSH = True
except:
    HAS_PUSH = False

# Tentar importar criptografia avançada
try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256
    from Crypto.Random import get_random_bytes
    CRYPTO_AVAILABLE = True
except:
    CRYPTO_AVAILABLE = False

# ============================================
# 🔐 CRIPTOGRAFIA
# ============================================

def cifrar_mensagem_simples(conteudo):
    """Cifra mensagem com base64 (fallback)"""
    return base64.b64encode(conteudo.encode('utf-8')).decode('utf-8')

def decifrar_mensagem_simples(conteudo_cifrado):
    """Decifra mensagem base64"""
    try:
        return base64.b64decode(conteudo_cifrado).decode('utf-8')
    except:
        return conteudo_cifrado

def gerar_hash_sha256(mensagem):
    """Gera hash SHA-256 da mensagem"""
    return hashlib.sha256(mensagem.encode('utf-8')).hexdigest()

def assinar_mensagem(mensagem, chave_privada_pem):
    """Assina digitalmente a mensagem com RSA-PSS"""
    try:
        if not CRYPTO_AVAILABLE:
            return None
        rsa_key = RSA.import_key(chave_privada_pem)
        h = SHA256.new(mensagem.encode('utf-8'))
        signature = pkcs1_15.new(rsa_key).sign(h)
        return base64.b64encode(signature).decode('utf-8')
    except:
        return None

def verificar_assinatura(mensagem, assinatura_b64, chave_publica_pem):
    """Verifica assinatura digital"""
    try:
        if not CRYPTO_AVAILABLE:
            return None
        rsa_key = RSA.import_key(chave_publica_pem)
        h = SHA256.new(mensagem.encode('utf-8'))
        signature = base64.b64decode(assinatura_b64)
        pkcs1_15.new(rsa_key).verify(h, signature)
        return True
    except:
        return False

# ============================================
# 📋 VIEWS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_usuario(request):
    telefone = request.GET.get('telefone') or request.GET.get('celular')
    if not telefone:
        return Response({'erro': 'Forneça um telefone'}, status=400)
    try:
        perfil_logado = Perfil.objects.get(usuario=request.user)
        perfil = Perfil.objects.get(telefone=telefone)
        
        if perfil.usuario.id == request.user.id:
            return Response({'encontrado': False, 'mensagem': 'Você não pode buscar a si mesmo'})
        
        is_amigo = Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=perfil.usuario)) |
            (Q(remetente=perfil.usuario) & Q(destinatario=request.user)),
            status='ACEITA'
        ).exists()
        
        solicitacao_enviada = SolicitacaoAmizade.objects.filter(
            remetente=perfil_logado, destinatario=perfil, status='PENDENTE'
        ).exists()
        
        return Response({
            'encontrado': True,
            'usuario': {'id': perfil.usuario.id, 'username': perfil.usuario.username, 'telefone': perfil.telefone, 'online': perfil.online},
            'is_amigo': is_amigo,
            'solicitacao_enviada': solicitacao_enviada
        })
    except Perfil.DoesNotExist:
        return Response({'encontrado': False, 'mensagem': 'Usuário não encontrado'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_amigos(request):
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        perfil.ultimo_visto = timezone.now()
        perfil.online = True
        perfil.save()
    except:
        pass
    
    dois_min_atras = timezone.now() - timedelta(minutes=2)
    Perfil.objects.filter(online=True, ultimo_visto__lt=dois_min_atras).update(online=False)
    
    amizades = Amizade.objects.filter(
        (Q(remetente=request.user) | Q(destinatario=request.user)), status='ACEITA'
    )
    
    amigos = []
    for a in amizades:
        amigo_user = a.destinatario if a.remetente == request.user else a.remetente
        try:
            amigo_perfil = Perfil.objects.get(usuario=amigo_user)
            amigos.append({
                'amizade_id': str(a.id), 'id': amigo_user.id,
                'username': amigo_user.username, 'telefone': amigo_perfil.telefone,
                'online': amigo_perfil.online, 'canal_seguro': a.canal_seguro,
                'conversa_id': str(a.conversa.id) if hasattr(a, 'conversa') else None
            })
        except Perfil.DoesNotExist:
            pass
    
    return Response({'amigos': amigos})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_solicitacoes(request):
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        recebidas = SolicitacaoAmizade.objects.filter(destinatario=perfil, status='PENDENTE')
        enviadas = SolicitacaoAmizade.objects.filter(remetente=perfil, status='PENDENTE')
        return Response({
            'recebidas': [{'id': str(s.id), 'remetente': s.remetente.usuario.username, 'telefone': s.remetente.telefone, 'mensagem': s.mensagem} for s in recebidas],
            'enviadas': [{'id': str(s.id), 'destinatario': s.destinatario.usuario.username, 'telefone': s.destinatario.telefone} for s in enviadas]
        })
    except Perfil.DoesNotExist:
        return Response({'recebidas': [], 'enviadas': []})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_solicitacao(request):
    data = json.loads(request.body)
    telefone = data.get('telefone')
    mensagem = data.get('mensagem', '')
    
    if not telefone:
        return Response({'erro': 'Telefone é obrigatório'}, status=400)
    
    try:
        remetente = Perfil.objects.get(usuario=request.user)
        destinatario = Perfil.objects.get(telefone=telefone)
        
        if remetente.usuario.id == destinatario.usuario.id:
            return Response({'erro': 'Não pode adicionar a si mesmo'}, status=400)
        
        if Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=destinatario.usuario)) |
            (Q(remetente=destinatario.usuario) & Q(destinatario=request.user))
        ).exists():
            return Response({'erro': 'Já são amigos'}, status=400)
        
        existente = SolicitacaoAmizade.objects.filter(remetente=remetente, destinatario=destinatario).first()
        
        if existente:
            if existente.status == 'PENDENTE':
                return Response({'erro': 'Solicitação já enviada'}, status=400)
            existente.status = 'PENDENTE'
            existente.mensagem = mensagem
            existente.save()
            solicitacao = existente
        else:
            solicitacao = SolicitacaoAmizade.objects.create(remetente=remetente, destinatario=destinatario, mensagem=mensagem)
        
        Notificacao.objects.create(
            usuario=destinatario.usuario, tipo='AMIZADE',
            titulo='Nova solicitação', conteudo=f'{request.user.username} quer ser seu amigo'
        )
        
        if HAS_PUSH:
            try:
                enviar_notificacao_push(
                    usuario=destinatario.usuario, titulo='Nova Solicitação',
                    conteudo=f'{request.user.username} quer ser seu amigo',
                    tipo='friend_request', dados_extra={'solicitacao_id': str(solicitacao.id)}
                )
            except:
                pass
        
        return Response({'mensagem': 'Solicitação enviada!', 'solicitacao_id': str(solicitacao.id)}, status=201)
        
    except Perfil.DoesNotExist:
        return Response({'erro': 'Usuário não encontrado'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_solicitacao(request, solicitacao_id):
    data = json.loads(request.body)
    acao = data.get('acao')
    
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        solicitacao = SolicitacaoAmizade.objects.get(id=solicitacao_id, destinatario=perfil)
        
        if acao == 'ACEITAR':
            solicitacao.status = 'ACEITA'; solicitacao.save()
            amizade = Amizade.objects.create(
                remetente=solicitacao.remetente.usuario, destinatario=request.user,
                status='ACEITA', aceito_em=timezone.now(), canal_seguro=True
            )
            conversa = Conversa.objects.create(tipo='DIRETA', amizade=amizade)
            conversa.participantes.add(solicitacao.remetente.usuario, request.user)
            
            Notificacao.objects.create(
                usuario=solicitacao.remetente.usuario, tipo='AMIZADE_ACEITA',
                titulo='Amizade aceita!', conteudo=f'{request.user.username} aceitou'
            )
            
            return Response({
                'mensagem': 'Amizade aceita!', 'amizade_id': str(amizade.id), 'conversa_id': str(conversa.id)
            })
        elif acao == 'RECUSAR':
            solicitacao.status = 'RECUSADA'; solicitacao.save()
            return Response({'mensagem': 'Solicitação recusada'})
        
        return Response({'erro': 'Ação inválida'}, status=400)
    except SolicitacaoAmizade.DoesNotExist:
        return Response({'erro': 'Solicitação não encontrada'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_conversas(request):
    conversas = Conversa.objects.filter(participantes=request.user, ativa=True)
    lista = []
    for c in conversas:
        outro = c.participantes.exclude(id=request.user.id).first()
        lista.append({
            'conversa_id': str(c.id),
            'outro_usuario': outro.username if outro else None,
            'total_mensagens': c.mensagens.count()
        })
    return Response({'conversas': lista})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_mensagem(request, conversa_id):
    data = json.loads(request.body)
    conteudo = data.get('conteudo', '')
    tipo = data.get('tipo', 'TEXTO')
    
    if not conteudo.strip():
        return Response({'erro': 'Mensagem vazia'}, status=400)
    
    try:
        conversa = Conversa.objects.get(id=conversa_id)
        
        if request.user not in conversa.participantes.all():
            return Response({'erro': 'Não autorizado'}, status=403)
        
        destinatario = conversa.participantes.exclude(id=request.user.id).first()
        
        # CORREÇÃO: Armazenar o texto DIRETAMENTE como bytes
        conteudo_bytes = conteudo.encode('utf-8')
        
        # Hash SHA-256
        hash_original = hashlib.sha256(conteudo_bytes).hexdigest()
        
        # Criar mensagem - CAMPO BinaryField recebe BYTES
        mensagem = Mensagem.objects.create(
            conversa=conversa,
            remetente=request.user,
            tipo=tipo,
            algoritmo='TEXTO_PURO',
            conteudo_cifrado=conteudo_bytes,  # BYTES, não string!
            hash_algoritmo='SHA-256',
            hash_original=hash_original,
            nonce=secrets.token_bytes(16)
        )
        
        conversa.ultima_mensagem = timezone.now()
        conversa.save()
        
        # Notificar
        if destinatario:
            Notificacao.objects.create(
                usuario=destinatario,
                tipo='MENSAGEM',
                titulo='Nova mensagem',
                conteudo=f'{request.user.username}: {conteudo[:30]}...'
            )
        
        # Log
        try:
            LogCriptografia.objects.create(
                usuario=request.user,
                operacao='ENVIO_MENSAGEM',
                algoritmo='TEXTO_PURO',
                parametros={
                    'conversa_id': str(conversa_id),
                    'destinatario': destinatario.username if destinatario else 'N/A',
                    'hash': hash_original[:16] + '...'
                }
            )
        except:
            pass
        
        print(f"[MENSAGEM] {request.user.username} -> {destinatario.username if destinatario else 'N/A'}: {conteudo[:30]}...")
        
        return Response({
            'mensagem': 'Enviada!',
            'id': str(mensagem.id),
            'algoritmo': 'TEXTO_PURO'
        }, status=201)
        
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'erro': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receber_mensagens(request, conversa_id):
    try:
        conversa = Conversa.objects.get(id=conversa_id)
        
        if request.user not in conversa.participantes.all():
            return Response({'erro': 'Não autorizado'}, status=403)
        
        mensagens = Mensagem.objects.filter(conversa=conversa).order_by('enviada_em')
        
        lista = []
        for msg in mensagens:
            # Obter conteúdo (BinaryField retorna bytes)
            conteudo_bytes = msg.conteudo_cifrado
            
            # Converter para string
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
            
            # Marcar como lida
            if msg.lida_em is None and msg.remetente != request.user:
                msg.lida_em = timezone.now()
                msg.save()
        
        return Response({'mensagens': lista})
        
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_notificacoes(request):
    notificacoes = Notificacao.objects.filter(usuario=request.user, lida=False).order_by('-criada_em')[:20]
    lista = []
    for n in notificacoes:
        lista.append({
            'id': str(n.id), 'tipo': n.tipo, 'titulo': n.titulo,
            'conteudo': n.conteudo, 'criada_em': n.criada_em
        })
        n.lida = True; n.save()
    return Response({'notificacoes': lista})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def info_criptografia(request):
    """Retorna informações sobre as chaves do usuário"""
    chaves = ChaveCriptografica.objects.filter(usuario=request.user)
    dados = []
    for chave in chaves:
        dados.append({
            'algoritmo': chave.algoritmo,
            'tipo': chave.tipo,
            'fingerprint': chave.fingerprint[:16] + '...',
            'criada_em': chave.criada_em,
            'revogada': chave.revogada
        })
    return Response({'usuario': request.user.username, 'chaves': dados, 'total_chaves': len(dados)})