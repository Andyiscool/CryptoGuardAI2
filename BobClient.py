"""
File: BobClient.py
Author: Andy Xiao

Description:
Client for sending encrypted emails to Alice's SMTP server.

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
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

def show_privacy_notice():
    print("""
CryptoGuardAI Privacy Notice

- We collect your email address, password, and email content to provide secure email services.
- Your data is encrypted in transit and at rest.
- Emails can be deleted immediately or retained for a period you specify.
- After the retention period, emails are permanently deleted from all databases.
- You have the right to access, correct, or delete your data at any time.
- For questions or requests, contact: privacy@yourdomain.com

By using this service, you agree to this policy.
""")  
    
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

def delete_email(email_id, port):
    try:
        retention_minutes = input("Enter Retention Minutes (default 1):")
        retention_minutes = int(retention_minutes) if retention_minutes.strip() else 1
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)  # Receive welcome message
        command = f"DELETE:{email_id}:{retention_minutes}\n"
        client_socket.sendall(command.encode('utf-8'))
        response = client_socket.recv(1024).decode('utf-8')
        print(f"Server response: {response}")
    except Exception as e:
        print(f"Error sending deletion request: {e}")
    finally:
        client_socket.close()
def hard_delete_email(email_id, port):
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='localhost')
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)
        command = f"HARD_DELETE:{email_id}\n"
        client_socket.sendall(command.encode("utf-8"))
        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
    except Exception as e:
        print(f"Error sending hard deletion request: {e}")
    finally:
        client_socket.close()
def retain_email(email_id, retention_days, port):
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)  # Receive welcome message
        command = f"RETAIN:{email_id}:{retention_days}\n"
        client_socket.sendall(command.encode('utf-8'))
        response = client_socket.recv(1024).decode('utf-8')
        print(f"Server response: {response}")
    except Exception as e:
        print(f"Error sending retention request: {e}")
    finally:
        client_socket.close()

def interactive_menu(port):
    while True:
        print("\nOptions:")
        print("1. Delete an email")
        print("2. Retain an email")
        print("3. Hard delete an email")
        print("4. Exit")
        choice = input("Enter your choice: ")
        if choice == '1':
            email_id = input("Enter the email ID to delete: ")
            delete_email(email_id, port)
        elif choice == '2':
            email_id = input("Enter the email ID to retain: ")
            retention_days = int(input("Enter the number of days to retain: "))
            retain_email(email_id, retention_days, port)
        elif choice == '3':
            email_id = input("Enter the email ID to hard delete: ")
            hard_delete_email(email_id, port)
        elif choice == '4':
            print("Exiting the menu.")
            break
        else:
            print("Invalid choice. Please try again.")

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
                message_content, "/Users/andyxiao/PostGradProjects/CryptoGuardAI/Alice_public_key.pem"
            )

        # Debugging encrypted components
            print(f"Encrypted AES key (Base64): {base64.b64encode(encrypted_aes_key).decode('utf-8')}")
            print(f"IV (Base64): {base64.b64encode(iv).decode('utf-8')}")
            print(f"Encrypted message (Base64): {base64.b64encode(encrypted_message).decode('utf-8')}")

        # Construct email data
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
    show_privacy_notice()
    print("1. Send email")
    print("2. Manage email retention/deletion")
    choice = input("Enter your choice: ")
    if choice == "1":
        send_email(
            recipient="alice@example.com",
            sender="bob@example.com",
            password="Securepass123!",
            message_content="Hello Alice, this is Bob!",
            port=2525
        )
    elif choice == "2":
        # Use the POP3 port (e.g., 1102)
        interactive_menu(2526)
    else:
        print("Invalid choice.")