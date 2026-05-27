"""
Funções Hash - SHA-256, SHA3-512, BLAKE3
"""
import hashlib

class HashService:
    @staticmethod
    def sha256(data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def sha3_512(data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha3_512(data).hexdigest()
    
    @staticmethod
    def blake3(data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        try:
            import blake3
            return blake3.blake3(data).hexdigest()
        except ImportError:
            # Fallback para SHA-256 se BLAKE3 não estiver instalado
            return hashlib.sha256(data).hexdigest()