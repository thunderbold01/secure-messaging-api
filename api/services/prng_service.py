"""
PRNG 128 bits - Gerador de Números Pseudoaleatórios
====================================================
Implementação acadêmica para geração de variáveis aleatórias
de 128 bits para uso no Diffie-Hellman e outros algoritmos.
"""
import secrets

class PRNG128:
    """Gerador de números aleatórios de 128 bits"""
    
    def __init__(self):
        self.bits = 128
        self.bytes = 16
    
    def generate(self):
        """Gera 16 bytes aleatórios (128 bits)"""
        return secrets.token_bytes(self.bytes)
    
    def generate_int(self):
        """Gera um inteiro de 128 bits"""
        return int.from_bytes(self.generate(), 'big')
    
    def generate_hex(self):
        """Gera representação hexadecimal"""
        return self.generate().hex()
    
    def get_entropy_source(self):
        """Retorna informações sobre a fonte de entropia"""
        return {
            'algorithm': 'System CSPRNG (secrets module)',
            'bits': self.bits,
            'bytes': self.bytes
        }