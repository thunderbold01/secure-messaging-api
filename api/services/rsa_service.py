"""
RSA-1024 - Criptografia Assimétrica
"""
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from typing import Tuple, Dict

class RSA1024:
    def __init__(self):
        self.key_size = 1024
    
    def generate_keypair(self) -> Tuple[Dict, Dict]:
        key = RSA.generate(self.key_size)
        public_key = {'n': key.n, 'e': key.e, 'size': self.key_size}
        private_key = {'n': key.n, 'e': key.e, 'd': key.d, 'p': key.p, 'q': key.q}
        return public_key, private_key
    
    def encrypt(self, message: bytes, public_key: Dict) -> bytes:
        rsa_key = RSA.construct((public_key['n'], public_key['e']))
        cipher = PKCS1_OAEP.new(rsa_key, hashAlgo=SHA256)
        return cipher.encrypt(message)
    
    def decrypt(self, ciphertext: bytes, private_key: Dict) -> bytes:
        rsa_key = RSA.construct(
            (private_key['n'], private_key['e'], private_key['d']),
            consistency_check=True
        )
        cipher = PKCS1_OAEP.new(rsa_key, hashAlgo=SHA256)
        return cipher.decrypt(ciphertext)