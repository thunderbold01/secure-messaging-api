import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

print("Gerando chaves VAPID...")

# Gerar par de chaves - CORRIGIDO: SECP256R1 (maiúsculo)
private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()

# Serializar chave privada
priv_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Serializar chave pública
pub_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Converter para base64 URL-safe
def pem_to_vapid(pem_bytes):
    # Remover cabeçalhos PEM
    pem_str = pem_bytes.decode()
    pem_str = pem_str.replace('-----BEGIN PRIVATE KEY-----\n', '')
    pem_str = pem_str.replace('-----BEGIN PUBLIC KEY-----\n', '')
    pem_str = pem_str.replace('\n-----END PRIVATE KEY-----', '')
    pem_str = pem_str.replace('\n-----END PUBLIC KEY-----', '')
    pem_str = pem_str.replace('\n', '')
    
    # Decodificar base64 padrão e re-codificar para URL-safe
    raw = base64.b64decode(pem_str)
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')

vapid_public = pem_to_vapid(pub_pem)
vapid_private = pem_to_vapid(priv_pem)

print("=" * 60)
print("CHAVES VAPID - Copie para seu settings.py")
print("=" * 60)
print(f"\nVAPID_PUBLIC_KEY = '{vapid_public}'")
print(f"\nVAPID_PRIVATE_KEY = '{vapid_private}'")
print("\nWEBPUSH_SETTINGS = {")
print("    'VAPID_PUBLIC_KEY': '{}',".format(vapid_public))
print("    'VAPID_PRIVATE_KEY': '{}',".format(vapid_private))
print("    'VAPID_ADMIN_EMAIL': 'admin@seuapp.com'")
print("}")
print("=" * 60)