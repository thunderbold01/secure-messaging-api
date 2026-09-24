import os
import sys
import time
import socket
import threading
import webbrowser
import shutil


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
    protocol = 'http'

    print()
    print('=' * 50)
    print('      CHATTING - Mensagens Seguras')
    print('=' * 50)
    print()
    print(f'  Servidor:    {protocol}://{local_ip}:{port}')
    print(f'  Frontend:    {protocol}://{local_ip}:{port}/')
    print(f'  Admin:       {protocol}://{local_ip}:{port}/admin.html')
    print(f'  API:         {protocol}://{local_ip}:{port}/api/')
    print(f'  SSL:         DESABILITADO (somente HTTP)')
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

    subprocess.run([
        sys.executable, '-m', 'daphne',
        '-b', '0.0.0.0',
        '-p', str(port),
        'core.asgi:application'
    ], cwd=base_dir)


if __name__ == '__main__':
    main()
