import os
import sys
import time
import socket
import threading
import webbrowser
import shutil
import ssl


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_internal_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_ssl_paths():
    base_dir = get_base_dir()
    cert_path = os.path.join(base_dir, 'ssl', 'cert.pem')
    key_path = os.path.join(base_dir, 'ssl', 'key.pem')

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print('[SSL] Certificados encontrados')
        return cert_path, key_path

    try:
        from generate_ssl import generate_ssl_cert
        cert_path, key_path = generate_ssl_cert()
        if cert_path and key_path:
            print('[SSL] Certificados gerados automaticamente')
            return cert_path, key_path
    except Exception:
        pass

    print('[SSL] AVISO: HTTPS nao disponivel. Use generate_ssl.py para gerar certificados.')
    return None, None


def main():
    base_dir = get_base_dir()
    internal_dir = get_internal_dir()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    os.environ['DEBUG'] = 'True'

    sys.path.insert(0, internal_dir)

    import django
    django.setup()

    from django.conf import settings

    db_path = os.path.join(base_dir, 'db.sqlite3')
    settings.DATABASES['default']['NAME'] = db_path

    frontend_src = os.path.join(internal_dir, 'frontend')
    frontend_dst = os.path.join(base_dir, 'frontend')

    if not os.path.exists(frontend_dst) and os.path.exists(frontend_src):
        shutil.copytree(frontend_src, frontend_dst)

    settings.FRONTEND_DIR = frontend_dst

    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)

    local_ip = get_local_ip()
    port = 8000

    cert_path, key_path = get_ssl_paths()
    use_ssl = cert_path is not None and key_path is not None
    protocol = 'https' if use_ssl else 'http'

    print()
    print('=' * 50)
    print('      CHATTING - Mensagens Seguras')
    print('=' * 50)
    print()
    print(f'  Servidor:    {protocol}://{local_ip}:{port}')
    print(f'  Frontend:    {protocol}://{local_ip}:{port}/')
    print(f'  Admin:       {protocol}://{local_ip}:{port}/admin.html')
    print(f'  API:         {protocol}://{local_ip}:{port}/api/')
    if use_ssl:
        print(f'  SSL:         TLS 1.2+ (certificado autoassinado)')
    else:
        print(f'  SSL:         DESABILITADO (gere certificados com generate_ssl.py)')
    print()
    print(f'  Para outro PC na mesma rede:')
    print(f'  -> {protocol}://{local_ip}:{port}/')
    print()
    print('=' * 50)
    print()

    def open_browser():
        time.sleep(3)
        webbrowser.open(f'{protocol}://127.0.0.1:{port}/')

    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    import subprocess

    if use_ssl:
        rel_cert = os.path.relpath(cert_path, base_dir).replace('\\', '/')
        rel_key = os.path.relpath(key_path, base_dir).replace('\\', '/')
        ssl_endpoint = f'ssl:{port}:privateKey={rel_key}:certKey={rel_cert}:interface=0.0.0.0'
        subprocess.run([
            sys.executable, '-m', 'daphne',
            '-e', ssl_endpoint,
            'core.asgi:application'
        ], cwd=base_dir)
    else:
        subprocess.run([
            sys.executable, '-m', 'daphne',
            '-b', '0.0.0.0',
            '-p', str(port),
            'core.asgi:application'
        ], cwd=base_dir)


if __name__ == '__main__':
    main()
