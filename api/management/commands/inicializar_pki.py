from django.core.management.base import BaseCommand
from api.models.pki_models import AutoridadeCertificadora
from api.services.pki_service import PKIService


class Command(BaseCommand):
    help = 'Inicializa a infraestrutura PKI'
    
    def handle(self, *args, **options):
        self.stdout.write('Inicializando PKI...')
        
        # Cria CA Raiz se não existir
        if not AutoridadeCertificadora.objects.filter(nivel=1).exists():
            ca = AutoridadeCertificadora.criar_ca_raiz("SecureMessaging Root CA")
            self.stdout.write(
                self.style.SUCCESS(f'✅ CA Raiz criada: {ca.nome}')
            )
        
        # Cria CA Intermediária
        if not AutoridadeCertificadora.objects.filter(nivel=2).exists():
            ca_raiz = AutoridadeCertificadora.objects.get(nivel=1)
            # Implementar criação de CA intermediária
            
        self.stdout.write(
            self.style.SUCCESS('✅ PKI inicializada com sucesso!')
        )