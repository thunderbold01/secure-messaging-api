"""
Cifra Híbrida - RSA + AES-256-CBC
"""
import base64
import json
import logging
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from .rsa_service import RSA1024

logger = logging.getLogger(__name__)


class HybridCipher:
    """Cifra Híbrida: RSA-1024 + AES-256-CBC"""
    
    def __init__(self):
        self.aes_key_size = 32  # AES-256
        self.iv_size = 16
        self.algorithm = "HYBRID-RSA-AES-256-CBC"
    
    def encrypt_message(self, plaintext: str, recipient_public_key: dict) -> dict:
        """
        Cifra uma mensagem usando RSA + AES
        """
        rsa = RSA1024()
        
        # Converter para bytes
        if isinstance(plaintext, str):
            plaintext_bytes = plaintext.encode('utf-8')
        else:
            plaintext_bytes = plaintext
        
        # 1. Gerar chave AES-256 e IV
        aes_key = get_random_bytes(self.aes_key_size)
        iv = get_random_bytes(self.iv_size)
        
        # 2. Cifrar mensagem com AES-CBC
        cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
        padded_data = pad(plaintext_bytes, AES.block_size)
        ciphertext = cipher_aes.encrypt(padded_data)
        
        # 3. Cifrar chave AES com RSA do destinatário
        encrypted_key = rsa.encrypt(aes_key, recipient_public_key)
        
        # 4. Retornar pacote
        return {
            'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8'),
            'iv': base64.b64encode(iv).decode('utf-8'),
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'algorithm': self.algorithm
        }
    
    def decrypt_message(self, encrypted_package: dict, private_key: dict) -> str:
        """
        Decifra uma mensagem usando a chave privada RSA
        """
        rsa = RSA1024()
        
        try:
            # 1. Decifrar chave AES com RSA
            encrypted_key = base64.b64decode(encrypted_package['encrypted_key'])
            aes_key = rsa.decrypt(encrypted_key, private_key)
            
            # Verificar tamanho da chave AES
            if len(aes_key) != self.aes_key_size:
                logger.warning(f"Tamanho de chave AES incorreto: {len(aes_key)} bytes")
            
            # 2. Decifrar mensagem com AES
            iv = base64.b64decode(encrypted_package['iv'])
            ciphertext = base64.b64decode(encrypted_package['ciphertext'])
            
            cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
            decrypted_padded = cipher_aes.decrypt(ciphertext)
            
            # 3. Remover padding
            plaintext_bytes = unpad(decrypted_padded, AES.block_size)
            
            # 4. Retornar como string
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Erro na decifração: {str(e)}")
            raise ValueError(f"Falha na decifração: {str(e)}")