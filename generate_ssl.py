"""
Gera certificado SSL autoassinado para desenvolvimento.
Executar uma vez: python generate_ssl.py
"""
import os
import subprocess
import sys


def generate_ssl_cert():
    ssl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssl')
    os.makedirs(ssl_dir, exist_ok=True)

    cert_path = os.path.join(ssl_dir, 'cert.pem')
    key_path = os.path.join(ssl_dir, 'key.pem')

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f'[SSL] Certificados ja existem em {ssl_dir}')
        return cert_path, key_path

    try:
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', key_path,
            '-out', cert_path,
            '-days', '365', '-nodes',
            '-subj', '/CN=localhost/O=MensagemSegura/C=AO'
        ], check=True, capture_output=True)
        print(f'[SSL] Certificados gerados em {ssl_dir}')
        return cert_path, key_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: usar Python para gerar
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'MensagemSegura'),
                x509.NameAttribute(NameOID.COUNTRY_NAME, 'AO'),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName([
                    x509.DNSName('localhost'),
                    x509.IPAddress(
                        __import__('ipaddress').IPv4Address('127.0.0.1')
                    ),
                ]), critical=False)
                .sign(key, hashes.SHA256())
            )

            with open(key_path, 'wb') as f:
                f.write(key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption()
                ))
            with open(cert_path, 'wb') as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            print(f'[SSL] Certificados gerados via cryptography em {ssl_dir}')
            return cert_path, key_path
        except ImportError:
            print('[SSL] AVISO: openssl e cryptography nao disponiveis. HTTPS desabilitado.')
            return None, None


if __name__ == '__main__':
    generate_ssl_cert()
