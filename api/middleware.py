import logging

logger = logging.getLogger('api')


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'

        # Prevent MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'

        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy - restrict dangerous features
        response['Permissions-Policy'] = (
            'accelerometer=(), '
            'ambient-light-sensor=(), '
            'autoplay=(), '
            'battery=(), '
            'camera=(), '
            'cross-origin-isolated=(), '
            'display-capture=(), '
            'document-domain=(), '
            'encrypted-media=(), '
            'execution-while-not-rendered=(), '
            'execution-while-out-of-viewport=(), '
            'fullscreen=(), '
            'geolocation=(), '
            'gyroscope=(), '
            'keyboard-map=(), '
            'magnetometer=(), '
            'microphone=(), '
            'midi=(), '
            'navigation-override=(), '
            'payment=(), '
            'picture-in-picture=(), '
            'publickey-credentials-get=(), '
            'screen-wake-lock=(), '
            'sync-xhr=(self), '
            'usb=(), '
            'web-share=(), '
            'xr-spatial-tracking=()'
        )

        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' blob: data:; "
            "connect-src 'self' ws: wss: https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )

        # Cache control for API responses
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'

        return response


class AuthDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
