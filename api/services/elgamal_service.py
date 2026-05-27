"""
ElGamal-1024 - Criptografia Assimétrica
========================================
Implementação acadêmica do algoritmo ElGamal com chave de 1024 bits.

Funcionamento:
1. Geração de chaves:
   - Escolhe primo p de 1024 bits
   - Escolhe gerador g do grupo multiplicativo
   - Chave privada x (aleatório < p-1)
   - Chave pública y = g^x mod p

2. Cifração:
   - Escolhe k aleatório
   - c1 = g^k mod p
   - c2 = m * y^k mod p

3. Decifração:
   - s = c1^x mod p
   - m = c2 * s^(-1) mod p
"""
from Crypto.Util.number import getPrime
from Crypto.Random import get_random_bytes
import secrets
from typing import Tuple, Dict

class ElGamal1024:
    """Implementação ElGamal-1024"""
    
    def __init__(self):
        self.key_size = 1024
        self.algorithm = f"ElGamal-{self.key_size}"
    
    def generate_keypair(self) -> Tuple[Dict, Dict]:
        """Gera par de chaves ElGamal-1024"""
        p = getPrime(self.key_size)
        g = 2
        x = secrets.randbelow(p - 2) + 1
        y = pow(g, x, p)
        
        public_key = {
            'p': p,
            'g': g,
            'y': y,
            'size': self.key_size,
            'algorithm': self.algorithm
        }
        
        private_key = {
            'p': p,
            'g': g,
            'x': x,
            'y': y,
            'size': self.key_size,
            'algorithm': self.algorithm
        }
        
        return public_key, private_key
    
    def encrypt(self, message: bytes, public_key: Dict) -> Tuple[int, int]:
        """
        Cifra mensagem com ElGamal
        Retorna: (c1, c2)
        """
        p = public_key['p']
        g = public_key['g']
        y = public_key['y']
        
        m = int.from_bytes(message, 'big')
        if m >= p:
            raise ValueError(f"Mensagem deve ser menor que p ({p.bit_length()} bits)")
        
        k = secrets.randbelow(p - 2) + 1
        c1 = pow(g, k, p)
        c2 = (m * pow(y, k, p)) % p
        
        return c1, c2
    
    def decrypt(self, ciphertext: Tuple[int, int], private_key: Dict) -> bytes:
        """Decifra mensagem com ElGamal"""
        c1, c2 = ciphertext
        p = private_key['p']
        x = private_key['x']
        
        s = pow(c1, x, p)
        s_inv = pow(s, -1, p)
        m = (c2 * s_inv) % p
        
        byte_length = (m.bit_length() + 7) // 8
        return m.to_bytes(byte_length, 'big')