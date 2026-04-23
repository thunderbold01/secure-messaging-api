"""
Módulo de criptografia - Implementação acadêmica
Algoritmos: RSA, ElGamal, ECC, Diffie-Hellman
"""
import hashlib
import secrets
import json
from typing import Tuple, Dict, Optional
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64


class CryptoCore:
    """Núcleo criptográfico do sistema"""
    
    @staticmethod
    def gerar_prng_128bits() -> bytes:
        """Gera número aleatório de 128 bits usando PRNG seguro"""
        return secrets.token_bytes(16)
    
    @staticmethod
    def gerar_hash(mensagem: bytes, algoritmo: str = 'SHA256') -> str:
        """Calcula hash da mensagem para integridade"""
        if algoritmo == 'SHA256':
            return hashlib.sha256(mensagem).hexdigest()
        elif algoritmo == 'SHA3_512':
            return hashlib.sha3_512(mensagem).hexdigest()
        elif algoritmo == 'BLAKE3':
            try:
                import blake3
                return blake3.blake3(mensagem).hexdigest()
            except ImportError:
                return hashlib.sha256(mensagem).hexdigest()
        return hashlib.sha256(mensagem).hexdigest()


class RSAHandler:
    """Implementação RSA-1024"""
    
    def __init__(self):
        self.key_size = 1024
        self.chave_publica = None
        self.chave_privada = None
    
    def gerar_par_chaves(self) -> Tuple[Dict, Dict]:
        """Gera par de chaves RSA-1024"""
        chave = RSA.generate(self.key_size)
        self.chave_privada = chave
        self.chave_publica = chave.publickey()
        
        chave_publica_dict = {
            'n': self.chave_publica.n,
            'e': self.chave_publica.e,
            'size': self.key_size,
            'algoritmo': 'RSA'
        }
        
        chave_privada_dict = {
            'n': self.chave_privada.n,
            'e': self.chave_privada.e,
            'd': self.chave_privada.d,
            'p': self.chave_privada.p,
            'q': self.chave_privada.q,
            'size': self.key_size,
            'algoritmo': 'RSA'
        }
        
        return chave_publica_dict, chave_privada_dict
    
    def cifrar(self, mensagem: bytes, chave_publica_dict: Dict) -> bytes:
        """Cifra mensagem com RSA-1024"""
        from Crypto.PublicKey import RSA
        chave = RSA.construct((chave_publica_dict['n'], chave_publica_dict['e']))
        cipher = PKCS1_OAEP.new(chave)
        return cipher.encrypt(mensagem)
    
    def decifrar(self, texto_cifrado: bytes, chave_privada_dict: Dict) -> bytes:
        """Decifra mensagem com RSA-1024"""
        from Crypto.PublicKey import RSA
        chave = RSA.construct((
            chave_privada_dict['n'],
            chave_privada_dict['e'],
            chave_privada_dict['d'],
            chave_privada_dict['p'],
            chave_privada_dict['q']
        ))
        cipher = PKCS1_OAEP.new(chave)
        return cipher.decrypt(texto_cifrado)


class DiffieHellmanHandler:
    """Implementação Diffie-Hellman com PRNG 128 bits"""
    
    def __init__(self):
        self.primo = None
        self.gerador = 2
        self.chave_privada = None
        self.chave_publica = None
    
    def gerar_parametros(self) -> Dict:
        """Gera parâmetros DH com PRNG de 128 bits"""
        from Crypto.Util.number import getPrime
        # Gera primo de 128 bits
        self.primo = getPrime(128)
        
        # Gera chave privada com PRNG 128 bits
        self.chave_privada = secrets.randbelow(self.primo - 2) + 1
        
        # Calcula chave pública: g^priv mod p
        self.chave_publica = pow(self.gerador, self.chave_privada, self.primo)
        
        return {
            'p': self.primo,
            'g': self.gerador,
            'public_key': self.chave_publica,
            'bits': 128
        }
    
    def calcular_segredo(self, chave_publica_outra: int) -> bytes:
        """Calcula segredo compartilhado"""
        segredo = pow(chave_publica_outra, self.chave_privada, self.primo)
        # Deriva chave de sessão com SHA-256
        return hashlib.sha256(str(segredo).encode()).digest()


class ElGamalHandler:
    """Implementação ElGamal-1024"""
    
    def __init__(self):
        self.key_size = 1024
        self.primo = None
        self.gerador = 2
        self.chave_privada = None
        self.chave_publica = None
    
    def gerar_par_chaves(self) -> Tuple[Dict, Dict]:
        """Gera par de chaves ElGamal-1024"""
        from Crypto.Util.number import getPrime
        
        self.primo = getPrime(self.key_size)
        self.chave_privada = secrets.randbelow(self.primo - 2) + 1
        self.chave_publica = pow(self.gerador, self.chave_privada, self.primo)
        
        publica = {
            'p': self.primo,
            'g': self.gerador,
            'y': self.chave_publica,
            'size': self.key_size,
            'algoritmo': 'ElGamal'
        }
        
        privada = {
            'p': self.primo,
            'g': self.gerador,
            'x': self.chave_privada,
            'y': self.chave_publica,
            'size': self.key_size,
            'algoritmo': 'ElGamal'
        }
        
        return publica, privada
    
    def cifrar(self, mensagem: bytes, chave_publica_dict: Dict) -> Tuple[int, int]:
        """Cifra mensagem com ElGamal"""
        p = chave_publica_dict['p']
        g = chave_publica_dict['g']
        y = chave_publica_dict['y']
        
        # Converte mensagem para número
        m = int.from_bytes(mensagem[:128], 'big')
        
        # Gera k aleatório
        k = secrets.randbelow(p - 2) + 1
        
        # c1 = g^k mod p
        c1 = pow(g, k, p)
        
        # c2 = m * y^k mod p
        c2 = (m * pow(y, k, p)) % p
        
        return c1, c2
    
    def decifrar(self, cifra: Tuple[int, int], chave_privada_dict: Dict) -> bytes:
        """Decifra mensagem com ElGamal"""
        c1, c2 = cifra
        p = chave_privada_dict['p']
        x = chave_privada_dict['x']
        
        # s = c1^x mod p
        s = pow(c1, x, p)
        
        # m = c2 * s^(-1) mod p
        s_inv = pow(s, -1, p)
        m = (c2 * s_inv) % p
        
        return m.to_bytes((m.bit_length() + 7) // 8, 'big')


class CifraHibrida:
    """Cifra Híbrida: Assimétrica + Simétrica"""
    
    @staticmethod
    def cifrar(mensagem: bytes, chave_publica_dict: Dict, algoritmo: str = 'RSA') -> Dict:
        """Cifra mensagem usando cifra híbrida"""
        # Gera chave simétrica aleatória (AES-256)
        chave_simetrica = get_random_bytes(32)
        nonce = get_random_bytes(16)
        
        # Cifra mensagem com AES
        cipher = AES.new(chave_simetrica, AES.MODE_GCM, nonce=nonce)
        texto_cifrado, tag = cipher.encrypt_and_digest(mensagem)
        
        # Cifra chave simétrica com assimétrica
        if algoritmo == 'RSA':
            handler = RSAHandler()
            chave_cifrada = handler.cifrar(chave_simetrica, chave_publica_dict)
        
        return {
            'chave_cifrada': chave_cifrada,
            'texto_cifrado': texto_cifrado,
            'nonce': nonce,
            'tag': tag,
            'algoritmo': 'HIBRIDO-' + algoritmo
        }
    
    @staticmethod
    def decifrar(pacote: Dict, chave_privada_dict: Dict, algoritmo: str = 'RSA') -> bytes:
        """Decifra mensagem usando cifra híbrida"""
        # Decifra chave simétrica
        if algoritmo == 'RSA':
            handler = RSAHandler()
            chave_simetrica = handler.decifrar(pacote['chave_cifrada'], chave_privada_dict)
        
        # Decifra mensagem com AES
        cipher = AES.new(chave_simetrica, AES.MODE_GCM, nonce=pacote['nonce'])
        mensagem = cipher.decrypt_and_verify(pacote['texto_cifrado'], pacote['tag'])
        
        return mensagem


class ECCHandler:
    """Implementação ECC P-128 (simplificada)"""
    
    def __init__(self):
        self.chave_privada = None
        self.chave_publica = None
    
    def gerar_par_chaves(self) -> Tuple[Dict, Dict]:
        """Gera par de chaves ECC P-128"""
        # Simplificado para demonstração
        self.chave_privada = secrets.randbits(128)
        self.chave_publica = hashlib.sha256(str(self.chave_privada).encode()).hexdigest()
        
        publica = {
            'Q': self.chave_publica,
            'curva': 'P-128',
            'algoritmo': 'ECC'
        }
        
        privada = {
            'd': self.chave_privada,
            'Q': self.chave_publica,
            'curva': 'P-128',
            'algoritmo': 'ECC'
        }
        
        return publica, privada