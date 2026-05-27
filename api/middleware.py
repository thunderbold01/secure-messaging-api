class AuthDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"[MIDDLEWARE] Path: {request.path}")
        print(f"[MIDDLEWARE] User: {request.user}")
        print(f"[MIDDLEWARE] Auth: {request.user.is_authenticated}")
        print(f"[MIDDLEWARE] Session: {request.session.session_key}")
        print(f"[MIDDLEWARE] Cookies: {request.COOKIES}")
        
        response = self.get_response(request)
        return response