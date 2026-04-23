from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import secrets
import hashlib

from api.models.auth_models import Perfil
from api.models.crypto_models import ChaveCriptografica

try:
    from Crypto.PublicKey import RSA
    from Crypto.Util.number import getPrime
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        'sistema': 'Mensageiro Seguro',
        'status': 'online',
        'crypto_disponivel': CRYPTO_AVAILABLE,
    })

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def registro(request):
    """Registra usuário e gera TODAS as chaves criptográficas"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        telefone = data.get('telefone') or data.get('numero_celular')
        email = data.get('email', '')
        
        if not username or not password or not telefone:
            return Response({'erro': 'Username, password e telefone são obrigatórios'}, status=400)
        
        if User.objects.filter(username=username).exists():
            return Response({'erro': 'Username já existe'}, status=400)
        
        if Perfil.objects.filter(telefone=telefone).exists():
            return Response({'erro': 'Telefone já cadastrado'}, status=400)
        
        user = User.objects.create_user(username=username, password=password, email=email)
        
        # ============================================
        # GERAR TODAS AS CHAVES CRIPTOGRÁFICAS
        # ============================================
        if CRYPTO_AVAILABLE:
            # 1. RSA-1024
            try:
                chave_rsa = RSA.generate(1024)
                rsa_publica = {'n': str(chave_rsa.n), 'e': chave_rsa.e, 'size': 1024}
                rsa_privada = {'n': str(chave_rsa.n), 'e': chave_rsa.e, 'd': str(chave_rsa.d), 'p': str(chave_rsa.p), 'q': str(chave_rsa.q)}
                fp_rsa = hashlib.sha256(str(rsa_publica).encode()).hexdigest()
                
                ChaveCriptografica.objects.create(usuario=user, algoritmo='RSA-1024', tipo='PUBLICA', chave_data=json.dumps(rsa_publica), fingerprint=fp_rsa)
                ChaveCriptografica.objects.create(usuario=user, algoritmo='RSA-1024', tipo='PRIVADA', chave_data=json.dumps(rsa_privada), fingerprint=fp_rsa)
                print(f"[CHAVES] RSA-1024 geradas para {username}")
            except Exception as e:
                print(f"[ERRO] RSA-1024: {e}")
            
            # 2. RSA-2048
            try:
                chave_rsa_2048 = RSA.generate(2048)
                rsa_2048_pub = {'n': str(chave_rsa_2048.n), 'e': chave_rsa_2048.e, 'size': 2048}
                rsa_2048_priv = {'n': str(chave_rsa_2048.n), 'e': chave_rsa_2048.e, 'd': str(chave_rsa_2048.d), 'p': str(chave_rsa_2048.p), 'q': str(chave_rsa_2048.q)}
                fp_rsa_2048 = hashlib.sha256(str(rsa_2048_pub).encode()).hexdigest()
                
                ChaveCriptografica.objects.create(usuario=user, algoritmo='RSA-2048', tipo='PUBLICA', chave_data=json.dumps(rsa_2048_pub), fingerprint=fp_rsa_2048)
                ChaveCriptografica.objects.create(usuario=user, algoritmo='RSA-2048', tipo='PRIVADA', chave_data=json.dumps(rsa_2048_priv), fingerprint=fp_rsa_2048)
                print(f"[CHAVES] RSA-2048 geradas para {username}")
            except Exception as e:
                print(f"[ERRO] RSA-2048: {e}")
            
            # 3. ElGamal-1024
            try:
                p = getPrime(1024)
                g = 2
                x = secrets.randbelow(p-2) + 1
                y = pow(g, x, p)
                elgamal_pub = {'p': str(p), 'g': g, 'y': str(y), 'size': 1024}
                elgamal_priv = {'p': str(p), 'g': g, 'x': str(x), 'y': str(y), 'size': 1024}
                fp_elgamal = hashlib.sha256(str(elgamal_pub).encode()).hexdigest()
                
                ChaveCriptografica.objects.create(usuario=user, algoritmo='ElGamal-1024', tipo='PUBLICA', chave_data=json.dumps(elgamal_pub), fingerprint=fp_elgamal)
                ChaveCriptografica.objects.create(usuario=user, algoritmo='ElGamal-1024', tipo='PRIVADA', chave_data=json.dumps(elgamal_priv), fingerprint=fp_elgamal)
                print(f"[CHAVES] ElGamal-1024 geradas para {username}")
            except Exception as e:
                print(f"[ERRO] ElGamal-1024: {e}")
            
            # 4. Diffie-Hellman (parâmetros)
            try:
                p_dh = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
                g_dh = 2
                dh_params = {'p': str(p_dh), 'g': g_dh, 'bits': 2048}
                fp_dh = hashlib.sha256(str(dh_params).encode()).hexdigest()
                
                ChaveCriptografica.objects.create(usuario=user, algoritmo='DiffieHellman', tipo='PUBLICA', chave_data=json.dumps(dh_params), fingerprint=fp_dh, parametros_dh=json.dumps(dh_params))
                print(f"[CHAVES] Diffie-Hellman gerado para {username}")
            except Exception as e:
                print(f"[ERRO] Diffie-Hellman: {e}")
        
        # Criar perfil
        Perfil.objects.create(usuario=user, telefone=telefone, online=False)
        token, _ = Token.objects.get_or_create(user=user)
        
        print(f"[REGISTRO] {username} registrado com TODAS as chaves!")
        
        return Response({
            'mensagem': 'Usuário registrado com sucesso!',
            'token': token.key,
            'usuario': {'id': user.id, 'username': user.username, 'telefone': telefone},
            'chaves_geradas': ['RSA-1024', 'RSA-2048', 'ElGamal-1024', 'DiffieHellman']
        }, status=201)
        
    except json.JSONDecodeError:
        return Response({'erro': 'JSON inválido'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'erro': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login(request):
    try:
        data = json.loads(request.body)
        user = authenticate(username=data.get('username'), password=data.get('password'))
        if user:
            django_login(request, user)
            try:
                perfil = Perfil.objects.get(usuario=user)
                perfil.online = True
                perfil.ultimo_visto = timezone.now()
                perfil.save()
            except:
                Perfil.objects.create(usuario=user, telefone=f"{user.id}0000000"[:10], online=True)
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key, 'usuario': {'id': user.id, 'username': user.username}})
        return Response({'erro': 'Credenciais inválidas'}, status=401)
    except Exception as e:
        return Response({'erro': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def logout(request):
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        perfil.online = False
        perfil.save()
    except:
        pass
    try:
        request.user.auth_token.delete()
    except:
        pass
    django_logout(request)
    return Response({'mensagem': 'Logout realizado'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def perfil(request):
    try:
        perfil = Perfil.objects.get(usuario=request.user)
        return Response({'id': request.user.id, 'username': request.user.username, 'telefone': perfil.telefone, 'online': perfil.online})
    except:
        return Response({'erro': 'Perfil não encontrado'}, status=404)

@api_view(['GET'])
@permission_classes([AllowAny])
def crypto_test(request):
    prng = secrets.token_bytes(16)
    return Response({'status': 'online', 'crypto_disponivel': CRYPTO_AVAILABLE, 'prng': prng.hex()[:32]})