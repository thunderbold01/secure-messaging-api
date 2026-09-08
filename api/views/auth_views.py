from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
import json
import re

from api.models.auth_models import Perfil
from api.security import (
    AuditLogger, InputValidator, RateLimiter,
    validate_input_sanitize
)

try:
    from Crypto.PublicKey import RSA
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
        'versao': '2.0',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok'})


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def registro(request):
    ip_address = None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    if not RateLimiter.check_registration_rate_limit(ip_address):
        AuditLogger.log(
            'RATE_LIMITED',
            'Rate limit de registro atingido',
            request=request,
            nivel='WARNING',
            dados={'ip': ip_address}
        )
        return Response({'erro': 'Muitas tentativas. Aguarde alguns minutos.'}, status=429)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    sanitized, errors = validate_input_sanitize(data, {
        'username': {'type': 'str', 'required': True, 'max_length': 30,
                     'validator': InputValidator.validate_username,
                     'error_message': 'Username obrigatorio'},
        'password': {'type': 'str', 'required': True, 'max_length': 128,
                     'validator': InputValidator.validate_password,
                     'error_message': 'Password obrigatoria'},
        'telefone': {'type': 'str', 'required': True, 'max_length': 15,
                     'validator': InputValidator.validate_phone,
                     'error_message': 'Telefone obrigatorio'},
    })

    if errors:
        return Response({'erro': errors}, status=400)

    username = sanitized['username']
    password = sanitized['password']
    telefone = sanitized['telefone']

    if User.objects.filter(username=username).exists():
        AuditLogger.log(
            'REGISTER_FAILED',
            f'Tentativa de registro com username existente: {username}',
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Username ja existe'}, status=400)

    if Perfil.objects.filter(telefone=telefone).exists():
        AuditLogger.log(
            'REGISTER_FAILED',
            f'Tentativa de registro com telefone existente',
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Telefone ja cadastrado'}, status=400)

    user = User.objects.create_user(username=username, password=password)
    Perfil.objects.create(usuario=user, telefone=telefone, online=False)
    token, _ = Token.objects.get_or_create(user=user)

    AuditLogger.log(
        'REGISTER',
        f'Novo usuario registrado: {username}',
        usuario=user,
        request=request,
        dados={'telefone': telefone}
    )

    return Response({
        'mensagem': 'Usuario registrado!',
        'token': token.key,
        'usuario': {'id': user.id, 'username': user.username, 'telefone': telefone},
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login(request):
    ip_address = None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'erro': 'JSON invalido'}, status=400)

    login_id = data.get('username', '').strip()[:30]
    password = data.get('password', '')[:128]

    if not login_id or not password:
        return Response({'erro': 'Username e password obrigatorios'}, status=400)

    if InputValidator.check_xss(login_id) or InputValidator.check_xss(password):
        AuditLogger.log(
            'XSS_ATTEMPT',
            'XSS detectado no login',
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Credenciais invalidas'}, status=401)

    if InputValidator.check_sql_injection(login_id):
        AuditLogger.log(
            'SQL_INJECTION_ATTEMPT',
            f'SQL Injection detectado no login: {login_id[:50]}',
            request=request,
            nivel='CRITICAL'
        )
        return Response({'erro': 'Credenciais invalidas'}, status=401)

    identifier = f"{login_id}:{ip_address}"
    if RateLimiter.get_failed_attempts(identifier) >= 5:
        AuditLogger.log(
            'LOGIN_LOCKOUT',
            f'Login bloqueado por muitas tentativas: {login_id}',
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Conta bloqueada temporariamente. Aguarde 5 minutos.'}, status=429)

    if not RateLimiter.check_login_rate_limit(identifier):
        AuditLogger.log(
            'RATE_LIMITED',
            'Rate limit de login atingido',
            request=request,
            nivel='WARNING'
        )
        return Response({'erro': 'Muitas tentativas. Aguarde.'}, status=429)

    user = None
    if '@' in login_id:
        try:
            user_obj = User.objects.get(email=login_id)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None
    else:
        user = authenticate(username=login_id, password=password)

    if user is not None:
        RateLimiter.clear_failed_attempts(identifier)
        django_login(request, user)
        Perfil.objects.filter(usuario=user).update(online=True, ultimo_visto=timezone.now())
        token, _ = Token.objects.get_or_create(user=user)

        AuditLogger.log(
            'LOGIN_SUCCESS',
            f'Login realizado com sucesso',
            usuario=user,
            request=request
        )

        return Response({
            'token': token.key,
            'usuario': {'id': user.id, 'username': user.username}
        })
    else:
        attempts = RateLimiter.increment_failed_attempts(identifier)

        AuditLogger.log(
            'LOGIN_FAILED',
            f'Tentativa de login falhou para: {login_id} (tentativa {attempts})',
            request=request,
            nivel='WARNING',
            dados={'attempts': attempts}
        )

        if attempts >= 5:
            AuditLogger.log(
                'LOGIN_LOCKOUT',
                f'Conta bloqueada apos 5 tentativas: {login_id}',
                request=request,
                nivel='CRITICAL'
            )

        return Response({'erro': 'Credenciais invalidas'}, status=401)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def logout(request):
    AuditLogger.log(
        'LOGOUT',
        'Logout realizado',
        usuario=request.user,
        request=request
    )
    Perfil.objects.filter(usuario=request.user).update(online=False)
    Token.objects.filter(user=request.user).delete()
    django_logout(request)
    return Response({'mensagem': 'Logout realizado'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def perfil(request):
    try:
        perfil = Perfil.objects.only('telefone', 'online').get(usuario=request.user)
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'telefone': perfil.telefone,
            'online': perfil.online
        })
    except Perfil.DoesNotExist:
        return Response({'erro': 'Perfil nao encontrado'}, status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
def crypto_test(request):
    import secrets
    prng = secrets.token_bytes(16)
    return Response({
        'status': 'online',
        'crypto_disponivel': CRYPTO_AVAILABLE,
        'prng': prng.hex()[:32]
    })
