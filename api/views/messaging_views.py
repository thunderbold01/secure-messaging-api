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
from api.security import AuditLogger, InputValidator, validate_input_sanitize

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


def gerar_hash_sha256(mensagem: str) -> str:
    return hashlib.sha256(mensagem.encode('utf-8')).hexdigest()


def cifrar_mensagem_hibrida(conteudo: str, destinatario_id: int) -> dict:
    from api.services.hybrid_service import HybridCipher

    chave_pub = ChaveCriptografica.objects.filter(
        usuario_id=destinatario_id,
        algoritmo='RSA-1024',
        tipo='PUBLICA',
        revogada=False
    ).first()

    if not chave_pub:
        return None

    hybrid = HybridCipher()
    public_key_data = json.loads(chave_pub.chave_data)

    return hybrid.encrypt_message(conteudo, public_key_data)


def decifrar_mensagem_hibrida(pacote_cifrado: dict, usuario) -> str:
    from api.services.hybrid_service import HybridCipher

    try:
        chave_priv = ChaveCriptografica.objects.filter(
            usuario=usuario,
            algoritmo='RSA-1024',
            tipo='PRIVADA',
            revogada=False
        ).first()

        if not chave_priv:
            return "[ERRO: Voce nao possui chave privada]"

        hybrid = HybridCipher()
        private_key_data = json.loads(chave_priv.chave_data)

        mensagem_decifrada = hybrid.decrypt_message(pacote_cifrado, private_key_data)

        return mensagem_decifrada

    except ValueError as e:
        if "incorrect decryption" in str(e).lower():
            return "[ERRO: Falha na decifracao - chave incorreta]"
        return f"[ERRO: {str(e)}]"
    except Exception as e:
        return f"[ERRO: {str(e)}]"


def safe_decode(data):
    if data is None:
        return ''
    if isinstance(data, (bytes, bytearray)):
        return data.decode('utf-8', errors='replace')
    if isinstance(data, memoryview):
        return data.tobytes().decode('utf-8', errors='replace')
    if isinstance(data, str):
        return data
    return str(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_usuario(request):
    telefone = request.GET.get('telefone') or request.GET.get('celular')
    if not telefone:
        return Response({'erro': 'Forneça um telefone'}, status=400)

    telefone = telefone.strip()[:15]

    if InputValidator.check_xss(telefone) or InputValidator.check_sql_injection(telefone):
        AuditLogger.log(
            'INVALID_INPUT',
            'Input invalido na busca de usuario',
            usuario=request.user,
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Telefone invalido'}, status=400)

    try:
        perfil = Perfil.objects.select_related('usuario').only(
            'telefone', 'online', 'usuario__id', 'usuario__username'
        ).get(telefone=telefone)

        if perfil.usuario_id == request.user.id:
            return Response({'encontrado': False, 'mensagem': 'Voce nao pode buscar a si mesmo'})

        is_amigo = Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=perfil.usuario)) |
            (Q(remetente=perfil.usuario) & Q(destinatario=request.user)),
            status='ACEITA'
        ).exists()

        perfil_logado = Perfil.objects.only('id').get(usuario=request.user)
        solicitacao_enviada = SolicitacaoAmizade.objects.filter(
            remetente=perfil_logado, destinatario=perfil, status='PENDENTE'
        ).exists()

        tem_chave = ChaveCriptografica.objects.filter(
            usuario=perfil.usuario,
            algoritmo='RSA-1024',
            tipo='PUBLICA'
        ).exists()

        return Response({
            'encontrado': True,
            'usuario': {
                'id': perfil.usuario.id,
                'username': perfil.usuario.username,
                'telefone': perfil.telefone,
                'online': perfil.online,
                'tem_chave_publica': tem_chave
            },
            'is_amigo': is_amigo,
            'solicitacao_enviada': solicitacao_enviada
        })
    except Perfil.DoesNotExist:
        return Response({'encontrado': False, 'mensagem': 'Usuario nao encontrado'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_amigos(request):
    user_id = request.user.id

    Perfil.objects.filter(usuario_id=user_id).update(
        ultimo_visto=timezone.now(), online=True
    )

    Perfil.objects.filter(
        online=True,
        ultimo_visto__lt=timezone.now() - timedelta(minutes=2)
    ).update(online=False)

    amizades = Amizade.objects.filter(
        (Q(remetente_id=user_id) | Q(destinatario_id=user_id)),
        status='ACEITA'
    ).select_related('remetente', 'destinatario')

    amigos = []

    for a in amizades:
        amigo_id = a.destinatario_id if a.remetente_id == user_id else a.remetente_id
        amigo_user = a.destinatario if a.remetente_id == user_id else a.remetente

        try:
            amigo_perfil = Perfil.objects.select_related('usuario').get(usuario_id=amigo_id)
        except Perfil.DoesNotExist:
            continue

        conversa, created = Conversa.objects.get_or_create(
            amizade=a,
            defaults={'tipo': 'DIRETA'}
        )

        if created:
            conversa.participantes.add(amigo_user, request.user)

        if request.user not in conversa.participantes.all():
            conversa.participantes.add(request.user)

        if amigo_user not in conversa.participantes.all():
            conversa.participantes.add(amigo_user)

        amigos.append({
            'amizade_id': str(a.id),
            'id': amigo_id,
            'username': amigo_user.username,
            'telefone': amigo_perfil.telefone,
            'online': amigo_perfil.online,
            'canal_seguro': a.canal_seguro,
            'conversa_id': str(conversa.id)
        })

    return Response({'amigos': amigos})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_solicitacoes(request):
    try:
        perfil = Perfil.objects.only('id').get(usuario=request.user)

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
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    sanitized, errors = validate_input_sanitize(data, {
        'telefone': {'type': 'str', 'required': True, 'max_length': 15,
                     'validator': InputValidator.validate_phone},
        'mensagem': {'type': 'str', 'required': False, 'max_length': 200},
    })

    if errors:
        return Response({'erro': errors}, status=400)

    telefone = sanitized['telefone']
    mensagem = sanitized.get('mensagem', 'Ola! Gostaria de adicionar voce.')

    try:
        remetente = Perfil.objects.only('id', 'usuario_id').get(usuario=request.user)
        destinatario = Perfil.objects.select_related('usuario').only(
            'id', 'usuario__id', 'usuario__username', 'telefone'
        ).get(telefone=telefone)

        if remetente.usuario_id == destinatario.usuario_id:
            return Response({'erro': 'Nao pode adicionar a si mesmo'}, status=400)

        if Amizade.objects.filter(
            (Q(remetente=request.user) & Q(destinatario=destinatario.usuario)) |
            (Q(remetente=destinatario.usuario) & Q(destinatario=request.user))
        ).exists():
            return Response({'erro': 'Ja sao amigos'}, status=400)

        solicitacao, _ = SolicitacaoAmizade.objects.update_or_create(
            remetente=remetente, destinatario=destinatario,
            defaults={'mensagem': mensagem, 'status': 'PENDENTE'}
        )

        Notificacao.objects.create(
            usuario=destinatario.usuario, tipo='AMIZADE',
            titulo='Nova solicitacao de amizade',
            conteudo=f'{request.user.username} quer ser seu amigo'
        )

        AuditLogger.log(
            'FRIEND_REQUEST_SENT',
            f'Solicitacao de amizade enviada para {destinatario.usuario.username}',
            usuario=request.user,
            request=request
        )

        return Response({
            'mensagem': 'Solicitacao enviada!',
            'solicitacao_id': str(solicitacao.id)
        }, status=201)

    except Perfil.DoesNotExist:
        return Response({'erro': 'Usuario nao encontrado'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_solicitacao(request, solicitacao_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    acao = data.get('acao')
    if acao not in ['ACEITAR', 'RECUSAR']:
        return Response({'erro': 'Acao invalida'}, status=400)

    try:
        perfil = Perfil.objects.only('id').get(usuario=request.user)
        solicitacao = SolicitacaoAmizade.objects.select_related(
            'remetente__usuario'
        ).get(id=solicitacao_id, destinatario=perfil)

        if acao == 'ACEITAR':
            solicitacao.status = 'ACEITA'
            solicitacao.save()

            from api.services.dh_service import DiffieHellman

            dh = DiffieHellman()
            params = dh.generate_keypair()

            amizade = Amizade.objects.create(
                remetente=solicitacao.remetente.usuario,
                destinatario=request.user,
                status='ACEITA',
                aceito_em=timezone.now(),
                canal_seguro=True,
                dh_completo=True,
                dh_parametros_remetente=json.dumps(params)
            )

            conversa = Conversa.objects.create(tipo='DIRETA', amizade=amizade)
            conversa.participantes.add(solicitacao.remetente.usuario, request.user)

            LogCriptografia.objects.create(
                usuario=request.user,
                operacao='HANDSHAKE_DH',
                algoritmo='Diffie-Hellman',
                parametros={'amizade_id': str(amizade.id)}
            )

            Notificacao.objects.create(
                usuario=solicitacao.remetente.usuario,
                tipo='AMIZADE_ACEITA',
                titulo='Amizade aceita!',
                conteudo=f'{request.user.username} aceitou sua solicitacao'
            )

            AuditLogger.log(
                'FRIEND_REQUEST_ACCEPTED',
                f'Amizade aceita com {solicitacao.remetente.usuario.username}',
                usuario=request.user,
                request=request
            )

            return Response({
                'mensagem': 'Amizade aceita com canal seguro!',
                'amizade_id': str(amizade.id),
                'conversa_id': str(conversa.id)
            })

        elif acao == 'RECUSAR':
            SolicitacaoAmizade.objects.filter(id=solicitacao_id).update(status='RECUSADA')

            AuditLogger.log(
                'FRIEND_REQUEST_REJECTED',
                f'Solicitacao recusada de {solicitacao.remetente.usuario.username}',
                usuario=request.user,
                request=request
            )

            return Response({'mensagem': 'Solicitacao recusada'})

        return Response({'erro': 'Acao invalida'}, status=400)

    except SolicitacaoAmizade.DoesNotExist:
        return Response({'erro': 'Solicitacao nao encontrada'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_conversas(request):
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
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    conteudo = data.get('conteudo', '')
    tipo = data.get('tipo', 'TEXTO')

    if tipo not in ['TEXTO', 'IMAGEM', 'AUDIO', 'VIDEO', 'ARQUIVO']:
        return Response({'erro': 'Tipo invalido'}, status=400)

    is_valid, error_msg = InputValidator.validate_message(conteudo)
    if not is_valid:
        return Response({'erro': error_msg}, status=400)

    try:
        conversa = Conversa.objects.select_related('amizade').get(id=conversa_id)

        participantes = list(conversa.participantes.values_list('id', flat=True))
        if request.user.id not in participantes:
            AuditLogger.log(
                'IDOR_ATTEMPT',
                f'Tentativa de acesso a conversa {conversa_id} nao autorizada',
                usuario=request.user,
                request=request,
                nivel='WARNING'
            )
            return Response({'erro': 'Nao autorizado'}, status=403)

        destinatario_id = next((p for p in participantes if p != request.user.id), None)
        if not destinatario_id:
            return Response({'erro': 'Destinatario nao encontrado'}, status=404)

        pacote_cifrado = cifrar_mensagem_hibrida(conteudo, destinatario_id)

        if not pacote_cifrado:
            return Response({'erro': 'Destinatario nao possui chave publica'}, status=400)

        hash_original = gerar_hash_sha256(conteudo)
        nonce_value = secrets.token_hex(16)

        mensagem = Mensagem.objects.create(
            conversa=conversa,
            remetente_id=request.user.id,
            tipo=tipo,
            algoritmo=pacote_cifrado['algorithm'],
            conteudo_cifrado=json.dumps(pacote_cifrado).encode('utf-8'),
            hash_algoritmo='SHA-256',
            hash_original=hash_original,
            nonce=nonce_value.encode('utf-8'),
            texto_original=conteudo
        )

        Conversa.objects.filter(id=conversa_id).update(ultima_mensagem=timezone.now())

        LogCriptografia.objects.create(
            usuario=request.user,
            operacao='ENVIAR_MENSAGEM',
            algoritmo=pacote_cifrado['algorithm'],
            parametros={'conversa_id': str(conversa_id), 'tamanho': len(conteudo)}
        )

        Notificacao.objects.create(
            usuario_id=destinatario_id,
            tipo='MENSAGEM',
            titulo='Nova mensagem segura',
            conteudo=f'{request.user.username} enviou uma mensagem criptografada'
        )

        AuditLogger.log(
            'MESSAGE_SENT',
            f'Mensagem enviada na conversa {conversa_id}',
            usuario=request.user,
            request=request,
            dados={'conversa_id': str(conversa_id), 'tipo': tipo}
        )

        return Response({
            'mensagem': 'Mensagem enviada com seguranca!',
            'id': str(mensagem.id),
            'algoritmo': pacote_cifrado['algorithm'],
            'conteudo': conteudo,
            'enviada_em': mensagem.enviada_em,
            'remetente': request.user.username,
            'hash_verificado': True
        }, status=201)

    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa nao encontrada'}, status=404)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receber_mensagens(request, conversa_id):
    try:
        if not Conversa.objects.filter(id=conversa_id, participantes=request.user).exists():
            AuditLogger.log(
                'IDOR_ATTEMPT',
                f'Tentativa de acesso a mensagens da conversa {conversa_id}',
                usuario=request.user,
                request=request,
                nivel='WARNING'
            )
            return Response({'erro': 'Nao autorizado'}, status=403)

        mensagens = Mensagem.objects.filter(conversa_id=conversa_id).select_related('remetente').order_by('enviada_em')[:100]
        lista = []
        msg_ids_para_marcar = []

        for msg in mensagens:
            try:
                is_media = msg.tipo in ['IMAGEM', 'AUDIO', 'VIDEO', 'ARQUIVO']
                conteudo = None
                integridade_verificada = False

                if msg.remetente_id == request.user.id:
                    if msg.texto_original:
                        if is_media:
                            try:
                                dados = json.loads(msg.texto_original)
                                arquivo_base64 = dados.get('arquivo_base64', '')
                                metadados = dados.get('metadados', {})

                                mime_type = metadados.get('mime_type', 'application/octet-stream')
                                if msg.tipo == 'AUDIO':
                                    mime_type = 'audio/webm'
                                elif msg.tipo == 'IMAGEM':
                                    mime_type = 'image/jpeg'
                                elif msg.tipo == 'VIDEO':
                                    mime_type = 'video/mp4'

                                if arquivo_base64 and not arquivo_base64.startswith('data:'):
                                    conteudo = f"data:{mime_type};base64,{arquivo_base64}"
                                else:
                                    conteudo = arquivo_base64
                            except Exception:
                                conteudo = None
                        else:
                            conteudo = msg.texto_original
                    else:
                        conteudo = "[Voce enviou uma mensagem]"

                    integridade_verificada = True

                    if is_media and not conteudo:
                        conteudo = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Crect x='3' y='3' width='18' height='18' rx='2'%3E%3C/rect%3E%3Ccircle cx='8.5' cy='8.5' r='2.5'%3E%3C/circle%3E%3Cpolyline points='21 15 16 10 5 21'%3E%3C/polyline%3E%3C/svg%3E"

                else:
                    if msg.algoritmo.startswith('HYBRID'):
                        try:
                            conteudo_cifrado_str = safe_decode(msg.conteudo_cifrado)
                            pacote = json.loads(conteudo_cifrado_str)
                            decifrado = decifrar_mensagem_hibrida(pacote, request.user)

                            if is_media:
                                metadados_str = safe_decode(msg.metadados_cifrados)
                                metadados = json.loads(metadados_str) if metadados_str else {}
                                mime_type = metadados.get('mime_type', 'application/octet-stream')
                                if msg.tipo == 'AUDIO':
                                    mime_type = 'audio/webm'
                                elif msg.tipo == 'IMAGEM':
                                    mime_type = 'image/jpeg'
                                elif msg.tipo == 'VIDEO':
                                    mime_type = 'video/mp4'
                                conteudo = f"data:{mime_type};base64,{decifrado}"
                            else:
                                conteudo = decifrado

                            if not decifrado.startswith('[ERRO'):
                                hash_atual = gerar_hash_sha256(decifrado)
                                if msg.hash_original and hash_atual == msg.hash_original:
                                    integridade_verificada = True
                                else:
                                    if not is_media:
                                        conteudo = f"[ALERTA DE INTEGRIDADE] {conteudo[:50]}..."
                            else:
                                integridade_verificada = False
                        except Exception as e:
                            conteudo = f"[ERRO: {str(e)[:50]}]"
                    else:
                        conteudo_cifrado_str = safe_decode(msg.conteudo_cifrado)
                        conteudo = conteudo_cifrado_str

                nome_arquivo = None
                if is_media:
                    try:
                        if msg.remetente_id == request.user.id and msg.texto_original:
                            dados = json.loads(msg.texto_original)
                            nome_arquivo = dados.get('metadados', {}).get('nome', 'arquivo')
                        else:
                            metadados_str = safe_decode(msg.metadados_cifrados)
                            if metadados_str:
                                metadados = json.loads(metadados_str)
                                nome_arquivo = metadados.get('nome', 'arquivo')
                    except Exception:
                        nome_arquivo = 'arquivo'

                lista.append({
                    'id': str(msg.id),
                    'remetente': msg.remetente.username,
                    'conteudo': conteudo,
                    'tipo': msg.tipo,
                    'algoritmo': msg.algoritmo,
                    'enviada_em': msg.enviada_em,
                    'lida': msg.lida_em is not None,
                    'integridade_verificada': integridade_verificada,
                    'enviada_por_mim': msg.remetente_id == request.user.id,
                    'nome_arquivo': nome_arquivo
                })

                if msg.lida_em is None and msg.remetente_id != request.user.id:
                    msg_ids_para_marcar.append(msg.id)

            except Exception as e:
                lista.append({
                    'id': str(msg.id),
                    'remetente': msg.remetente.username,
                    'conteudo': f'[ERRO: {str(e)[:50]}]',
                    'tipo': msg.tipo,
                    'algoritmo': msg.algoritmo,
                    'enviada_em': msg.enviada_em,
                    'lida': False,
                    'integridade_verificada': False,
                    'enviada_por_mim': msg.remetente_id == request.user.id,
                    'nome_arquivo': None
                })

        if msg_ids_para_marcar:
            now = timezone.now()
            Mensagem.objects.filter(id__in=msg_ids_para_marcar).update(lida_em=now)

        return Response({'mensagens': lista})

    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_notificacoes(request):
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

    if ids_para_marcar:
        Notificacao.objects.filter(id__in=ids_para_marcar).update(lida=True)

    return Response({'notificacoes': lista})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def info_criptografia(request):
    chaves = ChaveCriptografica.objects.filter(usuario=request.user).only(
        'algoritmo', 'tipo', 'fingerprint', 'criada_em', 'revogada'
    )[:10]

    dados = [{
        'algoritmo': c.algoritmo,
        'tipo': c.tipo,
        'fingerprint': c.fingerprint[:16] + '...' if c.fingerprint else 'N/A',
        'criada_em': c.criada_em,
        'revogada': c.revogada
    } for c in chaves]

    tem_chave_publica = any(c.tipo == 'PUBLICA' and not c.revogada for c in chaves)
    tem_chave_privada = any(c.tipo == 'PRIVADA' and not c.revogada for c in chaves)

    return Response({
        'usuario': request.user.username,
        'chaves': dados,
        'total_chaves': len(dados),
        'tem_chave_publica': tem_chave_publica,
        'tem_chave_privada': tem_chave_privada,
        'criptografia_disponivel': tem_chave_publica and tem_chave_privada
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_mensagem_arquivo(request, conversa_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    tipo = data.get('tipo', 'IMAGEM')
    arquivo_base64 = data.get('arquivo_base64', '')
    nome_arquivo = data.get('nome_arquivo', 'arquivo')
    mime_type = data.get('mime_type', 'application/octet-stream')

    if tipo == 'AUDIO':
        mime_type = 'audio/webm'

    if not arquivo_base64:
        return Response({'erro': 'Arquivo nao fornecido'}, status=400)

    is_valid, error_msg = InputValidator.validate_file_upload(tipo, mime_type)
    if not is_valid:
        return Response({'erro': error_msg}, status=400)

    nome_arquivo = nome_arquivo[:200] if nome_arquivo else 'arquivo'
    if InputValidator.check_xss(nome_arquivo):
        nome_arquivo = 'arquivo'

    try:
        conversa = Conversa.objects.select_related('amizade').get(id=conversa_id)

        participantes = list(conversa.participantes.values_list('id', flat=True))
        if request.user.id not in participantes:
            AuditLogger.log(
                'IDOR_ATTEMPT',
                f'Tentativa de envio de arquivo na conversa {conversa_id}',
                usuario=request.user,
                request=request,
                nivel='WARNING'
            )
            return Response({'erro': 'Nao autorizado'}, status=403)

        destinatario_id = next((p for p in participantes if p != request.user.id), None)
        if not destinatario_id:
            return Response({'erro': 'Destinatario nao encontrado'}, status=404)

        arquivo_base64_completo = arquivo_base64

        arquivo_base64_puro = arquivo_base64
        if ',' in arquivo_base64:
            arquivo_base64_puro = arquivo_base64.split(',')[1]

        pacote_cifrado = cifrar_mensagem_hibrida(arquivo_base64_puro, destinatario_id)

        if not pacote_cifrado:
            return Response({'erro': 'Destinatario nao possui chave publica'}, status=400)

        hash_original = gerar_hash_sha256(arquivo_base64_puro)

        metadados = {
            'tipo': tipo,
            'nome': nome_arquivo,
            'tamanho': len(arquivo_base64_puro),
            'mime_type': mime_type
        }

        texto_original_data = {
            'arquivo_base64': arquivo_base64_completo,
            'metadados': metadados
        }

        mensagem = Mensagem.objects.create(
            conversa=conversa,
            remetente_id=request.user.id,
            tipo=tipo,
            algoritmo=pacote_cifrado['algorithm'],
            conteudo_cifrado=json.dumps(pacote_cifrado).encode('utf-8'),
            metadados_cifrados=json.dumps(metadados).encode('utf-8'),
            hash_algoritmo='SHA-256',
            hash_original=hash_original,
            nonce=secrets.token_hex(16).encode('utf-8'),
            texto_original=json.dumps(texto_original_data)
        )

        Conversa.objects.filter(id=conversa_id).update(ultima_mensagem=timezone.now())

        Notificacao.objects.create(
            usuario_id=destinatario_id,
            tipo='MENSAGEM',
            titulo=f'Nova {tipo.lower()}',
            conteudo=f'{request.user.username} enviou um(a) {tipo.lower()}'
        )

        AuditLogger.log(
            'FILE_SENT',
            f'Arquivo {tipo} enviado na conversa {conversa_id}',
            usuario=request.user,
            request=request,
            dados={'conversa_id': str(conversa_id), 'tipo': tipo, 'nome': nome_arquivo}
        )

        return Response({
            'mensagem': f'{tipo} enviado com seguranca!',
            'id': str(mensagem.id),
            'tipo': tipo,
            'nome': nome_arquivo,
            'algoritmo': pacote_cifrado['algorithm']
        }, status=201)

    except Conversa.DoesNotExist:
        return Response({'erro': 'Conversa nao encontrada'}, status=404)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def baixar_arquivo(request, mensagem_id):
    try:
        mensagem = Mensagem.objects.select_related('conversa').get(id=mensagem_id)

        if not mensagem.conversa.participantes.filter(id=request.user.id).exists():
            AuditLogger.log(
                'IDOR_ATTEMPT',
                f'Tentativa de download de arquivo nao autorizada: {mensagem_id}',
                usuario=request.user,
                request=request,
                nivel='WARNING'
            )
            return Response({'erro': 'Nao autorizado'}, status=403)

        if mensagem.tipo not in ['IMAGEM', 'AUDIO', 'VIDEO', 'ARQUIVO']:
            return Response({'erro': 'Esta mensagem nao contem arquivo'}, status=400)

        if mensagem.remetente_id == request.user.id and mensagem.texto_original:
            dados_originais = json.loads(mensagem.texto_original)
            arquivo_base64 = dados_originais.get('arquivo_base64', '')
            metadados = dados_originais.get('metadados', {})
        else:
            conteudo_cifrado_str = safe_decode(mensagem.conteudo_cifrado)
            pacote = json.loads(conteudo_cifrado_str)
            arquivo_base64 = decifrar_mensagem_hibrida(pacote, request.user)

            if arquivo_base64.startswith('[ERRO'):
                return Response({'erro': 'Falha ao decifrar arquivo'}, status=500)

            metadados_str = safe_decode(mensagem.metadados_cifrados)
            metadados = json.loads(metadados_str) if metadados_str else {}

        if not arquivo_base64:
            return Response({'erro': 'Arquivo nao encontrado'}, status=404)

        mime_type = metadados.get('mime_type', 'application/octet-stream')

        if mensagem.tipo == 'AUDIO':
            mime_type = 'audio/webm'

        data_url = f"data:{mime_type};base64,{arquivo_base64}"

        return Response({
            'arquivo_base64': data_url,
            'tipo': mensagem.tipo,
            'nome': metadados.get('nome', 'arquivo'),
            'tamanho': metadados.get('tamanho', 0)
        })

    except Mensagem.DoesNotExist:
        return Response({'erro': 'Mensagem nao encontrada'}, status=404)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)
