from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.cache import cache
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
    """API Root"""
    return Response({
        'sistema': 'Mensageiro Seguro',
        'status': 'online',
        'crypto_disponivel': CRYPTO_AVAILABLE,
        'versao': '2.0',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check rápido"""
    return Response({'status': 'ok'})


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def registro(request):
    """Registro de usuário"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        telefone = data.get('telefone') or data.get('numero_celular')
        email = data.get('email', '')
        
        if not username or not password or not telefone:
            return Response({'erro': 'Username, password e telefone obrigatórios'}, status=400)
        
        if User.objects.filter(username=username).exists():
            return Response({'erro': 'Username já existe'}, status=400)
        
        if Perfil.objects.filter(telefone=telefone).exists():
            return Response({'erro': 'Telefone já cadastrado'}, status=400)
        
        user = User.objects.create_user(username=username, password=password, email=email)
        Perfil.objects.create(usuario=user, telefone=telefone, online=False)
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'mensagem': 'Usuário registrado!',
            'token': token.key,
            'usuario': {'id': user.id, 'username': user.username, 'telefone': telefone},
        }, status=201)
        
    except json.JSONDecodeError:
        return Response({'erro': 'JSON inválido'}, status=400)
    except Exception as e:
        return Response({'erro': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login(request):
    """Login"""
    try:
        data = json.loads(request.body)
        user = authenticate(username=data.get('username'), password=data.get('password'))
        
        if user:
            django_login(request, user)
            Perfil.objects.filter(usuario=user).update(online=True, ultimo_visto=timezone.now())
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'usuario': {'id': user.id, 'username': user.username}
            })
        return Response({'erro': 'Credenciais inválidas'}, status=401)
    except Exception as e:
        return Response({'erro': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def logout(request):
    """Logout"""
    Perfil.objects.filter(usuario=request.user).update(online=False)
    Token.objects.filter(user=request.user).delete()
    django_logout(request)
    return Response({'mensagem': 'Logout realizado'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def perfil(request):
    """Perfil"""
    try:
        perfil = Perfil.objects.only('telefone', 'online').get(usuario=request.user)
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'telefone': perfil.telefone,
            'online': perfil.online
        })
    except Perfil.DoesNotExist:
        return Response({'erro': 'Perfil não encontrado'}, status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
def crypto_test(request):
    """Crypto test"""
    prng = secrets.token_bytes(16)
    return Response({
        'status': 'online',
        'crypto_disponivel': CRYPTO_AVAILABLE,
        'prng': prng.hex()[:32]
    })