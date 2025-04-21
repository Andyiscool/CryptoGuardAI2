"""
File: generate_keys.py
Author: Andy Xiao

Description:
Generate RSA Keys for Alice and Bob.

References:
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

bob_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

with open("recipient_private_key_Bob.pem", "wb") as private_file:
    private_file.write(
        bob_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
bob_public_key = bob_private_key.public_key()
with open("recipient_public_key_Bob.pem", "wb") as public_file:
    public_file.write(
        bob_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
alice_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
with open("recipient_private_key_Alice.pem", "wb") as private_file:
    private_file.write(
        alice_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
alice_public_key = alice_private_key.public_key()
with open("recipient_public_key_Alice.pem", "wb") as public_file:
    public_file.write(
        alice_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
print("RSA key pair generated successfully")
