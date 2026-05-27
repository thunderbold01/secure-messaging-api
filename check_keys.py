# check_keys.py
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from api.models.crypto_models import ChaveCriptografica
from api.services.rsa_service import RSA1024
from api.services.hybrid_service import HybridCipher

def verificar_chaves():
    print("Verificando chaves dos usuários...")
    
    for user in User.objects.all():
        print(f"\n👤 Usuário: {user.username}")
        
        chave_pub = ChaveCriptografica.objects.filter(
            usuario=user, tipo='PUBLICA', algoritmo='RSA-1024'
        ).first()
        
        chave_priv = ChaveCriptografica.objects.filter(
            usuario=user, tipo='PRIVADA', algoritmo='RSA-1024'
        ).first()
        
        if chave_pub:
            pub_data = json.loads(chave_pub.chave_data)
            print(f"  ✅ Chave pública: n={str(pub_data['n'])[:30]}...")
        else:
            print(f"  ❌ Sem chave pública")
        
        if chave_priv:
            priv_data = json.loads(chave_priv.chave_data)
            print(f"  ✅ Chave privada: d={str(priv_data['d'])[:30]}...")
        else:
            print(f"  ❌ Sem chave privada")

def testar_cifra_entre_usuarios():
    print("\n" + "="*50)
    print("Testando cifra entre Alice e Bob")
    print("="*50)
    
    alice = User.objects.filter(username='alice').first()
    bob = User.objects.filter(username='bob').first()
    
    if not alice or not bob:
        print("❌ Alice ou Bob não encontrados. Crie os usuários primeiro.")
        return
    
    # Pegar chaves
    chave_pub_bob = ChaveCriptografica.objects.filter(
        usuario=bob, tipo='PUBLICA'
    ).first()
    
    chave_priv_bob = ChaveCriptografica.objects.filter(
        usuario=bob, tipo='PRIVADA'
    ).first()
    
    if not chave_pub_bob or not chave_priv_bob:
        print("❌ Bob não tem chaves RSA")
        return
    
    pub_data = json.loads(chave_pub_bob.chave_data)
    priv_data = json.loads(chave_priv_bob.chave_data)
    
    # Testar cifra
    hybrid = HybridCipher()
    mensagem = "Mensagem de teste de Alice para Bob"
    
    print(f"\n📝 Mensagem original: {mensagem}")
    
    # Cifrar (simulando Alice)
    pacote = hybrid.encrypt_message(mensagem, pub_data)
    print(f"🔒 Pacote cifrado criado")
    
    # Decifrar (Bob)
    decifrada = hybrid.decrypt_message(pacote, priv_data)
    print(f"🔓 Mensagem decifrada: {decifrada}")
    
    if mensagem == decifrada:
        print("\n✅ TESTE PASSOU! Cifra funcionando entre Alice e Bob!")
    else:
        print("\n❌ TESTE FALHOU!")

if __name__ == "__main__":
    verificar_chaves()
    testar_cifra_entre_usuarios()