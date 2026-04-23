"""
Cifra Híbrida - RSA + AES-256-GCM
"""
import base64
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from .rsa_service import RSA1024

class HybridCipher:
    def __init__(self):
        self.rsa = RSA1024()
    
    def encrypt(self, message, rsa_public_key):
        # Gera chave AES-256
        aes_key = get_random_bytes(32)
        nonce = get_random_bytes(12)
        
        # Cifra mensagem com AES-GCM
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(message)
        
        # Cifra chave AES com RSA
        encrypted_key = self.rsa.encrypt(aes_key, rsa_public_key)
        
        return {
            'encrypted_key': base64.b64encode(encrypted_key).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'nonce': base64.b64encode(nonce).decode(),
            'tag': base64.b64encode(tag).decode()
        }
    
    def decrypt(self, package, rsa_private_key):
        # Decodifica
        encrypted_key = base64.b64decode(package['encrypted_key'])
        ciphertext = base64.b64decode(package['ciphertext'])
        nonce = base64.b64decode(package['nonce'])
        tag = base64.b64decode(package['tag'])
        
        # Decifra chave AES com RSA
        aes_key = self.rsa.decrypt(encrypted_key, rsa_private_key)
        
        # Decifra mensagem com AES-GCM
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        message = cipher.decrypt_and_verify(ciphertext, tag)
        
        return message