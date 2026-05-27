#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Habilitar modo de produção otimizado
    if os.environ.get('DEBUG', 'True') != 'True':
        import django
        django.setup()
        
        # Desabilitar middleware de debug
        from django.conf import settings
        if hasattr(settings, 'DEBUG') and not settings.DEBUG:
            import logging
            logging.getLogger('django').setLevel(logging.WARNING)
    
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()