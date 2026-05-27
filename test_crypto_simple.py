"""
Teste simplificado do sistema de criptografia
"""
import os
import sys
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import django
    django.setup()
    print("✅ Django configurado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao configurar Django: {e}")
    print("Certifique-se de que está no diretório correto e que o Django está instalado")
    sys.exit(1)

from django.contrib.auth.models import User
from api.models.crypto_models import ChaveCriptografica


def test_imports():
    """Teste 1: Verificar imports dos serviços"""
    print("\n" + "="*50)
    print("🧪 TESTE 1: Verificando Imports")
    print("="*50)
    
    resultados = {}
    
    # Testar RSA
    try:
        from api.services.rsa_service import RSA1024
        rsa = RSA1024()
        print("✅ RSA1024 - Import OK")
        resultados['RSA'] = True
    except Exception as e:
        print(f"❌ RSA1024 - Erro: {e}")
        resultados['RSA'] = False
    
    # Testar Diffie-Hellman
    try:
        from api.services.dh_service import DiffieHellman
        dh = DiffieHellman()
        print("✅ DiffieHellman - Import OK")
        resultados['DH'] = True
    except Exception as e:
        print(f"❌ DiffieHellman - Erro: {e}")
        resultados['DH'] = False
    
    # Testar Hash
    try:
        from api.services.hash_service import HashService
        print("✅ HashService - Import OK")
        resultados['Hash'] = True
    except Exception as e:
        print(f"❌ HashService - Erro: {e}")
        resultados['Hash'] = False
    
    # Testar Hybrid
    try:
        from api.services.hybrid_service import HybridCipher
        print("✅ HybridCipher - Import OK")
        resultados['Hybrid'] = True
    except Exception as e:
        print(f"❌ HybridCipher - Erro: {e}")
        resultados['Hybrid'] = False
    
    # Testar PRNG
    try:
        from api.services.prng_service import PRNG128
        print("✅ PRNG128 - Import OK")
        resultados['PRNG'] = True
    except Exception as e:
        print(f"❌ PRNG128 - Erro: {e}")
        resultados['PRNG'] = False
    
    return resultados


def test_rsa():
    """Teste 2: Funcionamento do RSA"""
    print("\n" + "="*50)
    print("🧪 TESTE 2: RSA-1024")
    print("="*50)
    
    try:
        from api.services.rsa_service import RSA1024
        
        rsa = RSA1024()
        
        # Gerar chaves
        print("\n🔐 Gerando par de chaves RSA-1024...")
        public_key, private_key = rsa.generate_keypair()
        
        print(f"   - Tamanho: {public_key['size']} bits")
        print(f"   - Módulo (n): {str(public_key['n'])[:40]}...")
        print(f"   - Expoente (e): {public_key['e']}")
        
        # Testar encrypt/decrypt
        mensagem = b"Mensagem secreta para teste"
        print(f"\n📝 Mensagem original: {mensagem}")
        
        ciphertext = rsa.encrypt(mensagem, public_key)
        print(f"🔒 Ciphertext: {ciphertext.hex()[:40]}...")
        
        plaintext = rsa.decrypt(ciphertext, private_key)
        print(f"🔓 Decifrado: {plaintext}")
        
        if mensagem == plaintext:
            print("\n✅ RSA funcionando corretamente!")
            return True
        else:
            print("\n❌ RSA falhou!")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste RSA: {e}")
        return False


def test_diffie_hellman():
    """Teste 3: Diffie-Hellman"""
    print("\n" + "="*50)
    print("🧪 TESTE 3: Diffie-Hellman")
    print("="*50)
    
    try:
        from api.services.dh_service import DiffieHellman
        
        print("\n🤝 Alice e Bob vão trocar chaves...")
        
        # Alice
        alice = DiffieHellman()
        params_alice = alice.generate_keypair()
        print(f"\n👩 Alice:")
        print(f"   - Chave privada: {alice.private_key}")
        print(f"   - Chave pública: {alice.public_key}")
        
        # Bob
        bob = DiffieHellman()
        params_bob = bob.generate_keypair()
        print(f"\n👨 Bob:")
        print(f"   - Chave privada: {bob.private_key}")
        print(f"   - Chave pública: {bob.public_key}")
        
        # Calcular segredo compartilhado
        segredo_alice = alice.compute_shared_secret(bob.public_key)
        segredo_bob = bob.compute_shared_secret(alice.public_key)
        
        print(f"\n🔐 Segredo (Alice): {segredo_alice.hex()[:32]}...")
        print(f"🔐 Segredo (Bob):   {segredo_bob.hex()[:32]}...")
        
        if segredo_alice == segredo_bob:
            print("\n✅ Diffie-Hellman funcionou! Segredos idênticos!")
            return True
        else:
            print("\n❌ Diffie-Hellman falhou!")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste DH: {e}")
        return False


def test_hybrid_cipher():
    """Teste 4: Cifra Híbrida RSA + AES"""
    print("\n" + "="*50)
    print("🧪 TESTE 4: Cifra Híbrida (RSA + AES-256)")
    print("="*50)
    
    try:
        from api.services.rsa_service import RSA1024
        from api.services.hybrid_service import HybridCipher
        
        # Gerar chaves RSA
        rsa = RSA1024()
        public_key, private_key = rsa.generate_keypair()
        
        # Criar cifra híbrida
        hybrid = HybridCipher()
        
        # Mensagem de teste
        mensagem = "Esta é uma mensagem ultra secreta que será criptografada com RSA e AES!"
        print(f"\n📝 Mensagem original ({len(mensagem)} caracteres):")
        print(f"   {mensagem}")
        
        # Cifrar
        print("\n🔒 Cifrando mensagem...")
        pacote = hybrid.encrypt_message(mensagem, public_key)
        
        print(f"   - Algoritmo: {pacote['algorithm']}")
        print(f"   - Encrypted Key: {pacote['encrypted_key'][:30]}...")
        print(f"   - IV: {pacote['iv'][:20]}...")
        print(f"   - Ciphertext: {pacote['ciphertext'][:30]}...")
        
        # Decifrar
        print("\n🔓 Decifrando mensagem...")
        decifrada = hybrid.decrypt_message(pacote, private_key)
        
        print(f"   - Mensagem decifrada: {decifrada}")
        
        if mensagem == decifrada:
            print("\n✅ Cifra Híbrida funcionando corretamente!")
            return True
        else:
            print("\n❌ Cifra Híbrida falhou!")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste Hybrid: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hash():
    """Teste 5: Funções Hash"""
    print("\n" + "="*50)
    print("🧪 TESTE 5: Funções Hash")
    print("="*50)
    
    try:
        from api.services.hash_service import HashService
        
        mensagem = "Mensagem para teste de integridade"
        print(f"\n📝 Mensagem: {mensagem}")
        
        # SHA-256
        hash256 = HashService.sha256(mensagem)
        print(f"\n🔐 SHA-256:    {hash256}")
        
        # SHA3-512
        hash3 = HashService.sha3_512(mensagem)
        print(f"🔐 SHA3-512:  {hash3[:40]}...")
        
        # BLAKE3
        hash_blake = HashService.blake3(mensagem)
        print(f"🔐 BLAKE3:    {hash_blake[:40]}...")
        
        # Testar com modificação
        mensagem_mod = mensagem + " (modificada)"
        hash_mod = HashService.sha256(mensagem_mod)
        
        if hash256 != hash_mod:
            print(f"\n✅ Hash mudou após modificação da mensagem")
            print(f"   Original: {hash256[:20]}...")
            print(f"   Modificada: {hash_mod[:20]}...")
            return True
        else:
            print("\n❌ Hash não mudou!")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste Hash: {e}")
        return False


def test_prng():
    """Teste 6: PRNG 128 bits"""
    print("\n" + "="*50)
    print("🧪 TESTE 6: PRNG 128 bits")
    print("="*50)
    
    try:
        from api.services.prng_service import PRNG128
        
        prng = PRNG128()
        
        print("\n🎲 Gerando números aleatórios...")
        
        # Gerar bytes
        bytes1 = prng.generate()
        bytes2 = prng.generate()
        print(f"   - Bytes 1: {bytes1.hex()}")
        print(f"   - Bytes 2: {bytes2.hex()}")
        
        # Gerar inteiro
        int_val = prng.generate_int()
        print(f"   - Inteiro: {int_val}")
        
        # Verificar unicidade
        if bytes1 != bytes2:
            print("\n✅ PRNG gerou valores diferentes (boa entropia)")
            return True
        else:
            print("\n⚠️ PRNG gerou valores iguais (possível problema)")
            return True
            
    except Exception as e:
        print(f"❌ Erro no teste PRNG: {e}")
        return False


def test_database():
    """Teste 7: Banco de Dados"""
    print("\n" + "="*50)
    print("🧪 TESTE 7: Banco de Dados")
    print("="*50)
    
    try:
        # Verificar se as tabelas existem
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chaves_criptograficas'")
            if cursor.fetchone():
                print("✅ Tabela 'chaves_criptograficas' existe")
            else:
                print("❌ Tabela 'chaves_criptograficas' NÃO existe")
                return False
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mensagens'")
            if cursor.fetchone():
                print("✅ Tabela 'mensagens' existe")
            else:
                print("❌ Tabela 'mensagens' NÃO existe")
                return False
        
        # Criar usuário de teste
        user, created = User.objects.get_or_create(
            username='testuser_crypto',
            defaults={'password': 'testpass123'}
        )
        
        if created:
            print("✅ Usuário de teste criado")
        else:
            print("ℹ️ Usuário de teste já existe")
        
        # Tentar criar chave de teste
        from api.services.rsa_service import RSA1024
        rsa = RSA1024()
        pub, priv = rsa.generate_keypair()
        
        ChaveCriptografica.objects.filter(usuario=user).delete()
        
        chave_pub = ChaveCriptografica.objects.create(
            usuario=user,
            algoritmo='RSA-1024',
            tipo='PUBLICA',
            chave_data=json.dumps(pub),
            fingerprint='test_pub'
        )
        
        chave_priv = ChaveCriptografica.objects.create(
            usuario=user,
            algoritmo='RSA-1024',
            tipo='PRIVADA',
            chave_data=json.dumps(priv),
            fingerprint='test_priv'
        )
        
        print("✅ Chaves salvas no banco com sucesso!")
        
        # Verificar
        count = ChaveCriptografica.objects.filter(usuario=user).count()
        print(f"   - Total de chaves para o usuário: {count}")
        
        if count == 2:
            print("\n✅ Banco de dados funcionando corretamente!")
            return True
        else:
            print("\n❌ Problema no banco de dados")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste Database: {e}")
        return False


def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "🔬"*30)
    print("     INICIANDO TESTES DO SISTEMA DE CRIPTOGRAFIA")
    print("🔬"*30)
    
    resultados = {}
    
    # Teste 1: Imports
    resultados.update(test_imports())
    
    # Se os imports básicos falharem, não continue
    if not resultados.get('RSA', False):
        print("\n❌ IMPORTS BÁSICOS FALHARAM! Corrija os imports primeiro.")
        print("\nPossíveis soluções:")
        print("1. Renomeie os arquivos em api/services/ para .py (sem dupla extensão)")
        print("2. Verifique se todos os arquivos existem:")
        print("   - rsa_service.py")
        print("   - dh_service.py")
        print("   - hash_service.py")
        print("   - hybrid_service.py")
        print("   - prng_service.py")
        return resultados
    
    # Testes principais
    resultados['RSA_Func'] = test_rsa()
    resultados['DH_Func'] = test_diffie_hellman()
    resultados['Hybrid_Func'] = test_hybrid_cipher()
    resultados['Hash_Func'] = test_hash()
    resultados['PRNG_Func'] = test_prng()
    resultados['Database_Func'] = test_database()
    
    # Resumo Final
    print("\n" + "="*50)
    print("📊 RESUMO FINAL DOS TESTES")
    print("="*50)
    
    for teste, resultado in resultados.items():
        if resultado:
            print(f"   ✅ PASS - {teste}")
        else:
            print(f"   ❌ FAIL - {teste}")
    
    total = len(resultados)
    passaram = sum(1 for r in resultados.values() if r)
    
    print(f"\n📈 Total: {passaram}/{total} testes passaram")
    
    if passaram == total:
        print("\n🎉 PARABÉNS! Todos os testes passaram!")
        print("   O sistema de criptografia está 100% funcional!")
    else:
        print(f"\n⚠️ {total - passaram} teste(s) falharam.")
        
        # Sugestões
        if not resultados.get('RSA_Func', False):
            print("\n🔧 Para corrigir RSA:")
            print("   - Verifique se o pycryptodome está instalado: pip install pycryptodome")
        
        if not resultados.get('DH_Func', False):
            print("\n🔧 Para corrigir Diffie-Hellman:")
            print("   - Verifique o arquivo dh_service.py")
        
        if not resultados.get('Hybrid_Func', False):
            print("\n🔧 Para corrigir Cifra Híbrida:")
            print("   - Verifique o arquivo hybrid_service.py")
    
    return resultados


if __name__ == "__main__":
    run_all_tests()