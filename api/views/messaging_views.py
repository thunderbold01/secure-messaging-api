from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import json
import secrets
import hashlib
import base64

from api.models.auth_models import Perfil
from api.models.messaging_models import SolicitacaoAmizade, Amizade, Conversa, Mensagem, Notificacao
from api.models.crypto_models import ChaveCriptografica

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    CRYPTO_AVAILABLE = True
except:
    CRYPTO_AVAILABLE = False

# ============================================
# FUNÇÕES AUXILIARES DE CRIPTOGRAFIA
# ============================================
def cifrar_rsa(mensagem, chave_publica):
    """Cifra mensagem com RSA-1024"""
    rsa_key = RSA.construct((int(chave_publica['n']), chave_publica['e']))
    cipher = PKCS1_OAEP.new(rsa_key)
    return cipher.encrypt(mensagem.encode())

def cifrar_elgamal(mensagem, chave_publica):
    """Cifra mensagem com ElGamal"""
    p = int(chave_publica['p'])
    g = chave_publica['g']
    y = int(chave_publica['y'])
    m = int.from_bytes(mensagem.encode()[:128], 'big')
    k = secrets.randbelow(p-2) + 1
    c1 = pow(g, k, p)
    c2 = (m * pow(y, k, p)) % p
    return json.dumps({'c1': str(c1), 'c2': str(c2)}).encode()

def cifrar_hibrido(mensagem, chave_publica):
    """Cifra híbrida RSA + AES-256-GCM"""
    chave_aes = get_random_bytes(32)
    nonce = get_random_bytes(12)
    cipher = AES.new(chave_aes, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(mensagem.encode())
    chave_cifrada = cifrar_rsa(chave_aes.decode('latin1'), chave_publica)
    return json.dumps({
        'chave': base64.b64encode(chave_cifrada).decode(),
        'dados': base64.b64encode(ciphertext).decode(),
        'nonce': base64.b64encode(nonce).decode(),
        'tag': base64.b64encode(tag).decode()
    }).encode()

# ============================================
# VIEWS
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
        is_amigo = Amizade.objects.filter((Q(remetente=request.user) & Q(destinatario=perfil.usuario)) | (Q(remetente=perfil.usuario) & Q(destinatario=request.user)), status='ACEITA').exists()
        return Response({'encontrado': True, 'usuario': {'id': perfil.usuario.id, 'username': perfil.usuario.username, 'telefone': perfil.telefone, 'online': perfil.online}, 'is_amigo': is_amigo})
    except Perfil.DoesNotExist:
        return Response({'encontrado': False})

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
    
    amizades = Amizade.objects.filter((Q(remetente=request.user) | Q(destinatario=request.user)), status='ACEITA')
    amigos = []
    for a in amizades:
        amigo_user = a.destinatario if a.remetente == request.user else a.remetente
        try:
            amigo_perfil = Perfil.objects.get(usuario=amigo_user)
            amigos.append({'id': amigo_user.id, 'username': amigo_user.username, 'telefone': amigo_perfil.telefone, 'online': amigo_perfil.online, 'canal_seguro': a.canal_seguro, 'conversa_id': str(a.conversa.id) if hasattr(a, 'conversa') else None})
        except:
            pass
    return Response({'amigos': amigos})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_solicitacoes(request):
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        recebidas = SolicitacaoAmizade.objects.filter(destinatario=perfil, status='PENDENTE')
        enviadas = SolicitacaoAmizade.objects.filter(remetente=perfil, status='PENDENTE')
        return Response({'recebidas': [{'id': str(s.id), 'remetente': s.remetente.usuario.username, 'telefone': s.remetente.telefone} for s in recebidas], 'enviadas': [{'id': str(s.id), 'destinatario': s.destinatario.usuario.username, 'telefone': s.destinatario.telefone} for s in enviadas]})
    except:
        return Response({'recebidas': [], 'enviadas': []})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_solicitacao(request):
    data = json.loads(request.body)
    telefone = data.get('telefone')
    try:
        remetente = Perfil.objects.get(usuario=request.user)
        destinatario = Perfil.objects.get(telefone=telefone)
        if Amizade.objects.filter((Q(remetente=request.user) & Q(destinatario=destinatario.usuario)) | (Q(remetente=destinatario.usuario) & Q(destinatario=request.user))).exists():
            return Response({'erro': 'Já são amigos'}, status=400)
        solicitacao, _ = SolicitacaoAmizade.objects.get_or_create(remetente=remetente, destinatario=destinatario, defaults={'mensagem': data.get('mensagem', '')})
        return Response({'mensagem': 'Solicitação enviada!', 'id': str(solicitacao.id)})
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
            solicitacao.status = 'ACEITA'
            solicitacao.save()
            amizade = Amizade.objects.create(remetente=solicitacao.remetente.usuario, destinatario=request.user, status='ACEITA', canal_seguro=True)
            conversa = Conversa.objects.create(tipo='DIRETA', amizade=amizade)
            conversa.participantes.add(solicitacao.remetente.usuario, request.user)
            return Response({'mensagem': 'Aceita!', 'conversa_id': str(conversa.id)})
        else:
            solicitacao.status = 'RECUSADA'
            solicitacao.save()
            return Response({'mensagem': 'Recusada'})
    except:
        return Response({'erro': 'Solicitação não encontrada'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_mensagem(request, conversa_id):
    data = json.loads(request.body)
    conteudo = data.get('conteudo', '')
    algoritmo = data.get('algoritmo', 'HIBRIDO')
    
    try:
        conversa = Conversa.objects.get(id=conversa_id)
        if request.user not in conversa.participantes.all():
            return Response({'erro': 'Não autorizado'}, status=403)
        
        # Obter chave pública do destinatário baseado no algoritmo escolhido
        destinatario = conversa.participantes.exclude(id=request.user.id).first()
        
        if algoritmo == 'RSA-1024':
            chave = ChaveCriptografica.objects.filter(usuario=destinatario, algoritmo='RSA-1024', tipo='PUBLICA').first()
            if chave:
                conteudo_cifrado = cifrar_rsa(conteudo, json.loads(chave.chave_data))
            else:
                algoritmo = 'HIBRIDO'
        
        if algoritmo == 'ElGamal-1024':
            chave = ChaveCriptografica.objects.filter(usuario=destinatario, algoritmo='ElGamal-1024', tipo='PUBLICA').first()
            if chave:
                conteudo_cifrado = cifrar_elgamal(conteudo, json.loads(chave.chave_data))
            else:
                algoritmo = 'HIBRIDO'
        
        if algoritmo == 'HIBRIDO':
            chave = ChaveCriptografica.objects.filter(usuario=destinatario, algoritmo='RSA-1024', tipo='PUBLICA').first()
            if chave:
                conteudo_cifrado = cifrar_hibrido(conteudo, json.loads(chave.chave_data))
            else:
                conteudo_cifrado = conteudo.encode()
                algoritmo = 'TEXTO_PURO'
        
        hash_original = hashlib.sha256(conteudo.encode()).hexdigest()
        
        mensagem = Mensagem.objects.create(
            conversa=conversa,
            remetente=request.user,
            tipo='TEXTO',
            algoritmo=algoritmo,
            conteudo_cifrado=conteudo_cifrado,
            hash_algoritmo='SHA-256',
            hash_original=hash_original,
            nonce=secrets.token_bytes(16)
        )
        
        conversa.ultima_mensagem = timezone.now()
        conversa.save()
        
        print(f"[MENSAGEM] {request.user.username} -> {destinatario.username} usando {algoritmo}")
        
        return Response({'mensagem': 'Enviada!', 'id': str(mensagem.id), 'algoritmo': algoritmo}, status=201)
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)

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
            conteudo = msg.conteudo_cifrado
            if isinstance(conteudo, bytes):
                try:
                    conteudo = conteudo.decode('utf-8')
                except:
                    conteudo = '[CRIPTOGRAFADO]'
            lista.append({'id': str(msg.id), 'remetente': msg.remetente.username, 'conteudo': conteudo, 'algoritmo': msg.algoritmo, 'enviada_em': msg.enviada_em})
            if msg.lida_em is None and msg.remetente != request.user:
                msg.lida_em = timezone.now()
                msg.save()
        return Response({'mensagens': lista})
    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa não encontrada'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_conversas(request):
    conversas = Conversa.objects.filter(participantes=request.user, ativa=True)
    lista = []
    for c in conversas:
        outro = c.participantes.exclude(id=request.user.id).first()
        lista.append({'conversa_id': str(c.id), 'outro_usuario': outro.username if outro else None, 'total_mensagens': c.mensagens.count()})
    return Response({'conversas': lista})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_notificacoes(request):
    notificacoes = Notificacao.objects.filter(usuario=request.user, lida=False)[:20]
    lista = []
    for n in notificacoes:
        lista.append({'id': str(n.id), 'tipo': n.tipo, 'titulo': n.titulo, 'conteudo': n.conteudo})
        n.lida = True
        n.save()
    return Response({'notificacoes': lista})