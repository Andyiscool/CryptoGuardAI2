"""
File: AliceClient.py
Author: Andy Xiao

Description:
Client for sending encrypted emails to Bob's SMTP server.

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""

import socket
import ssl
import base64
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import os

def hybrid_encrypt(message, recipient_public_key_path):
    """
    Encrypts the message using hybrid encryption (RSA + AES).
    """
    aes_key = os.urandom(32)  # 256-bit AES key
    iv = os.urandom(16)  # 128-bit IV

    # Encrypt AES key with recipient's public key
    with open(recipient_public_key_path, "rb") as key_file:
        public_key = serialization.load_pem_public_key(key_file.read())
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=SHA256()),
            algorithm=SHA256(),
            label=None,
        ),
    )

    # Encrypt the message with AES
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_message = padder.update(message.encode("utf-8")) + padder.finalize()
    encrypted_message = encryptor.update(padded_message) + encryptor.finalize()

    return encrypted_aes_key, iv, encrypted_message

def send_email(recipient, sender, password, message_content, port):
    """
    Sends an encrypted email using hybrid encryption.
    """
    context = ssl.create_default_context()
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False
    context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket = context.wrap_socket(client_socket, server_hostname='localhost')

    try:
        client_socket.connect(('localhost', port))

        # Encrypt the message
        try:
            encrypted_aes_key, iv, encrypted_message = hybrid_encrypt(
                message_content, "/Users/andyxiao/PostGradProjects/CryptoGuardAI/Bob_public_key.pem"
            )

            # Debugging encrypted components
            print(f"Encrypted AES key (Base64): {base64.b64encode(encrypted_aes_key).decode('utf-8')}")
            print(f"IV (Base64): {base64.b64encode(iv).decode('utf-8')}")
            print(f"Encrypted message (Base64): {base64.b64encode(encrypted_message).decode('utf-8')}")
       
            email_data = (
                f"From: {sender}\nTo: {recipient}\n".encode("utf-8")
                + b"Encrypted-AES-Key: " + base64.b64encode(encrypted_aes_key) + b"\n"
                + b"IV: " + base64.b64encode(iv) + b"\n"
                + b"Message: " + base64.b64encode(encrypted_message) + b"\n"
            )
        except Exception as e:
            print(f"Error constructing email data: {e}")
            return

        # Debug email data
        print(f"Constructed email data:\n{email_data.decode('utf-8')}")

        # Send email
        client_socket.sendall(email_data)
        print(client_socket.recv(1024).decode("utf-8"))
    except ssl.SSLError as e:
        print(f"SSL error: {e}")
    except ConnectionError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()
if __name__ == "__main__":
    send_email(
        recipient="bob@example.com",
        sender="alice@example.com",
        password="Securepass123!",
        message_content="Hello Bob, this is Alice!",
        port=2525
    )