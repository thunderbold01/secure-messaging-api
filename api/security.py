import re
import logging
import hashlib
import secrets
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

logger = logging.getLogger('api')
security_logger = logging.getLogger('django.security')

User = get_user_model()


class AuditLogger:
    """Sistema de auditoria centralizado"""

    EVENTOS = {
        'LOGIN_SUCCESS': 'LOGIN_SUCCESS',
        'LOGIN_FAILED': 'LOGIN_FAILED',
        'LOGIN_LOCKOUT': 'LOGIN_LOCKOUT',
        'LOGOUT': 'LOGOUT',
        'REGISTER': 'REGISTER',
        'PASSWORD_CHANGE': 'PASSWORD_CHANGE',
        'TOKEN_CREATED': 'TOKEN_CREATED',
        'TOKEN_REVOKED': 'TOKEN_REVOKED',
        'MESSAGE_SENT': 'MESSAGE_SENT',
        'FILE_SENT': 'FILE_SENT',
        'FRIEND_REQUEST_SENT': 'FRIEND_REQUEST_SENT',
        'FRIEND_REQUEST_ACCEPTED': 'FRIEND_REQUEST_ACCEPTED',
        'FRIEND_REQUEST_REJECTED': 'FRIEND_REQUEST_REJECTED',
        'ACCESS_DENIED': 'ACCESS_DENIED',
        'RATE_LIMITED': 'RATE_LIMITED',
        'INVALID_INPUT': 'INVALID_INPUT',
        'CSRF_FAILED': 'CSRF_FAILED',
        'XSS_ATTEMPT': 'XSS_ATTEMPT',
        'SQL_INJECTION_ATTEMPT': 'SQL_INJECTION_ATTEMPT',
        'IDOR_ATTEMPT': 'IDOR_ATTEMPT',
        'ADMIN_ACTION': 'ADMIN_ACTION',
        'CRYPTO_KEY_GENERATED': 'CRYPTO_KEY_GENERATED',
        'CRYPTO_KEY_REVOKED': 'CRYPTO_KEY_REVOKED',
        'SECURITY_HEADERS_MISSING': 'SECURITY_HEADERS_MISSING',
    }

    @classmethod
    def log(cls, evento, descricao, usuario=None, request=None, dados=None, nivel='INFO'):
        ip_address = None
        user_agent = None
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]

        log_data = {
            'evento': evento,
            'descricao': descricao,
            'nivel': nivel,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'dados': dados or {},
        }

        if usuario:
            log_data['usuario_id'] = usuario.id
            log_data['username'] = usuario.username

        log_message = f"[{nivel}] {evento}: {descricao}"
        if ip_address:
            log_message += f" | IP: {ip_address}"
        if usuario:
            log_message += f" | User: {usuario.username}"

        if nivel == 'CRITICAL' or nivel == 'SECURITY':
            logger.critical(log_message)
        elif nivel == 'ERROR':
            logger.error(log_message)
        elif nivel == 'WARNING':
            logger.warning(log_message)
        else:
            logger.info(log_message)

        try:
            from api.models.pki_models import LogSeguranca
            LogSeguranca.objects.create(
                nivel=nivel,
                evento=evento,
                descricao=descricao,
                usuario=usuario,
                ip_address=ip_address,
                dados=log_data,
            )
        except Exception as e:
            logger.error(f"Falha ao salvar log de auditoria: {e}")

    @classmethod
    def _get_client_ip(cls, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class InputValidator:
    """Validador de entrada centralizado"""

    XSS_PATTERNS = [
        re.compile(r'<script\b', re.IGNORECASE),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe\b', re.IGNORECASE),
        re.compile(r'<object\b', re.IGNORECASE),
        re.compile(r'<embed\b', re.IGNORECASE),
        re.compile(r'<link\b', re.IGNORECASE),
        re.compile(r'<style\b', re.IGNORECASE),
        re.compile(r'expression\s*\(', re.IGNORECASE),
        re.compile(r'url\s*\(', re.IGNORECASE),
        re.compile(r'<img\b[^>]+onerror', re.IGNORECASE),
        re.compile(r'<svg\b[^>]+onload', re.IGNORECASE),
    ]

    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|DECLARE|TRUNCATE)\b)", re.IGNORECASE),
        re.compile(r"(--|;|\/\*|\*\/|xp_)", re.IGNORECASE),
        re.compile(r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"('|\"|;)--", re.IGNORECASE),
        re.compile(r"CHAR\s*\(", re.IGNORECASE),
        re.compile(r"CONCAT\s*\(", re.IGNORECASE),
    ]

    @classmethod
    def check_xss(cls, value):
        if not isinstance(value, str):
            return False
        for pattern in cls.XSS_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @classmethod
    def check_sql_injection(cls, value):
        if not isinstance(value, str):
            return False
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @classmethod
    def sanitize_string(cls, value, max_length=1000):
        if not isinstance(value, str):
            return value
        value = value[:max_length]
        value = value.replace('\x00', '')
        return value.strip()

    @classmethod
    def validate_username(cls, username):
        if not username or not isinstance(username, str):
            return False, 'Username obrigatorio'
        username = username.strip()
        if len(username) < 3 or len(username) > 30:
            return False, 'Username deve ter entre 3 e 30 caracteres'
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            return False, 'Username so pode conter letras, numeros, _, . e -'
        if cls.check_xss(username):
            return False, 'Username contem caracteres nao permitidos'
        return True, None

    @classmethod
    def validate_phone(cls, phone):
        if not phone or not isinstance(phone, str):
            return False, 'Telefone obrigatorio'
        clean = re.sub(r'\D', '', phone)
        if len(clean) < 9 or len(clean) > 15:
            return False, 'Telefone deve ter entre 9 e 15 digitos'
        return True, None

    @classmethod
    def validate_password(cls, password):
        if not password or not isinstance(password, str):
            return False, 'Password obrigatoria'
        if len(password) < 8:
            return False, 'Password deve ter pelo menos 8 caracteres'
        if len(password) > 128:
            return False, 'Password muito longa'
        if not re.search(r'[a-z]', password):
            return False, 'Password deve conter letra minuscula'
        if not re.search(r'[A-Z]', password):
            return False, 'Password deve conter letra maiuscula'
        if not re.search(r'[0-9]', password):
            return False, 'Password deve conter pelo menos um numero'
        common = ['password', '12345678', 'qwerty123', 'admin123', 'letmein', 'welcome1']
        if password.lower() in common:
            return False, 'Password muito comum'
        return True, None

    @classmethod
    def validate_message(cls, content):
        if not content or not isinstance(content, str):
            return False, 'Mensagem obrigatoria'
        content = content.strip()
        if len(content) == 0:
            return False, 'Mensagem vazia'
        if len(content) > 5000:
            return False, 'Mensagem muito longa (maximo 5000 caracteres)'
        if cls.check_xss(content):
            AuditLogger.log(
                'XSS_ATTEMPT',
                'Tentativa de XSS detectada em mensagem',
                nivel='WARNING',
                dados={'preview': content[:100]}
            )
            return False, 'Mensagem contem caracteres nao permitidos'
        return True, None

    @classmethod
    def validate_file_upload(cls, file_type, mime_type, file_size=None):
        allowed_types = {
            'IMAGEM': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'VIDEO': ['video/mp4', 'video/webm', 'video/ogg'],
            'AUDIO': ['audio/webm', 'audio/ogg', 'audio/mpeg', 'audio/wav'],
            'ARQUIVO': ['application/pdf', 'text/plain', 'application/zip',
                       'application/msword',
                       'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        }
        if file_type not in allowed_types:
            return False, 'Tipo de arquivo invalido'
        if mime_type and mime_type not in allowed_types[file_type]:
            return False, 'Tipo de MIME nao permitido'
        if file_size and file_size > 10 * 1024 * 1024:
            return False, 'Arquivo muito grande (maximo 10MB)'
        return True, None


class RateLimiter:
    """Rate limiter baseado em cache"""

    @classmethod
    def check_rate_limit(cls, key, max_requests, window_seconds):
        cache_key = f'ratelimit:{key}'
        current = cache.get(cache_key, 0)
        if current >= max_requests:
            return False
        cache.set(cache_key, current + 1, window_seconds)
        return True

    @classmethod
    def check_login_rate_limit(cls, identifier):
        return cls.check_rate_limit(f'login:{identifier}', max_requests=5, window_seconds=300)

    @classmethod
    def check_api_rate_limit(cls, user_id):
        return cls.check_rate_limit(f'api:{user_id}', max_requests=100, window_seconds=60)

    @classmethod
    def check_registration_rate_limit(cls, ip_address):
        return cls.check_rate_limit(f'register:{ip_address}', max_requests=3, window_seconds=3600)

    @classmethod
    def increment_failed_attempts(cls, identifier):
        key = f'failed_login:{identifier}'
        attempts = cache.get(key, 0)
        cache.set(key, attempts + 1, 300)
        return attempts + 1

    @classmethod
    def get_failed_attempts(cls, identifier):
        return cache.get(f'failed_login:{identifier}', 0)

    @classmethod
    def clear_failed_attempts(cls, identifier):
        cache.delete(f'failed_login:{identifier}')


def require_authentication(view_func):
    """Decorator para exigir autenticacao"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            AuditLogger.log(
                'ACCESS_DENIED',
                f'Acesso nao autenticado a {request.path}',
                request=request,
                nivel='WARNING'
            )
            return JsonResponse({'erro': 'Autenticacao obrigatoria'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin(view_func):
    """Decorator para exigir permissao de admin"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({'erro': 'Autenticacao obrigatoria'}, status=401)
        if not request.user.is_staff and not request.user.is_superuser:
            AuditLogger.log(
                'ACCESS_DENIED',
                f'Tentativa de acesso admin por {request.user.username}',
                usuario=request.user,
                request=request,
                nivel='WARNING'
            )
            return JsonResponse({'erro': 'Permissao negada'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def validate_input_sanitize(data, fields_config):
    """
    Valida e sanitiza dados de entrada.
    fields_config: dict com {field_name: {'type': str, 'required': bool, 'max_length': int, 'validator': callable}}
    """
    errors = {}
    sanitized = {}

    for field_name, config in fields_config.items():
        value = data.get(field_name)

        if config.get('required', False) and (value is None or (isinstance(value, str) and not value.strip())):
            errors[field_name] = config.get('error_message', f'{field_name} obrigatorio')
            continue

        if value is None:
            sanitized[field_name] = config.get('default', None)
            continue

        if isinstance(value, str):
            max_len = config.get('max_length', 1000)
            value = value[:max_len].strip()
            value = value.replace('\x00', '')

        if InputValidator.check_xss(str(value)):
            AuditLogger.log(
                'XSS_ATTEMPT',
                f'XSS detectado no campo {field_name}',
                nivel='WARNING',
                dados={'field': field_name, 'value_preview': str(value)[:50]}
            )
            errors[field_name] = 'Caracteres nao permitidos'
            continue

        if InputValidator.check_sql_injection(str(value)):
            AuditLogger.log(
                'SQL_INJECTION_ATTEMPT',
                f'SQL Injection detectado no campo {field_name}',
                nivel='WARNING',
                dados={'field': field_name, 'value_preview': str(value)[:50]}
            )
            errors[field_name] = 'Caracteres nao permitidos'
            continue

        validator = config.get('validator')
        if validator:
            is_valid, error_msg = validator(value)
            if not is_valid:
                errors[field_name] = error_msg
                continue

        sanitized[field_name] = value

    return sanitized, errors
