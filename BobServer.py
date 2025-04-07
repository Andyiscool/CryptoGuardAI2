"""
File: BobServer.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""

import socket
import ssl
import threading
from collections import defaultdict
from user_management import users, register_user, authenticate_user
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.backends import default_backend
from argon2 import PasswordHasher

import os
import logging
import base64
logging.basicConfig(filename='server.log', level=logging.INFO)
ph = PasswordHasher()

messages = defaultdict(list)
AES_KEY = os.urandom(32)  # 256-bit key
AES_IV = os.urandom(16)   # 128-bit IV
def aes_encrypt(data):
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return encrypted_data
def aes_decrypt(encrypted_data):
    if isinstance(encrypted_data, str):
        encrypted_data = encrypted_data.encode('utf-8')
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    data = unpadder.update(decrypted_data) + unpadder.finalize()
    return data
def authenticate(client_socket):
    logging.info("Authentication attempt started.")
    client_socket.send(b"+OK Enter username:\n")
    username = client_socket.recv(1024).decode("utf-8").strip()
    client_socket.send(b"+OK Enter password:\n")
    password = client_socket.recv(1024).decode("utf-8").strip()
    if authenticate_user(username, password):
        logging.info(f"Authentication successful for user: {username}")
        client_socket.send(b"+OK Authentication successful\n")
        return username
    else:
        logging.warning(f"Authentication failed for user: {username}")
        client_socket.send(b"-ERR Authentication failed\n")
        return None
#send email
def handle_smtp_client(client_socket):
    try:
        username = authenticate(client_socket)
        if not username:
            return
        client_socket.send(b"220 SMTP server ready\n")
        email_data = client_socket.recv(1024).decode("utf-8")
        lines = email_data.split('\n')
        recipients = []  # Use a list to store multiple recipients
        sender = None
        message_body = []
        file_attachment = None

        for line in lines:
            if line.startswith("To:"):
                # Parse multiple recipients separated by commas
                recipients = [recipient.strip() for recipient in line.split(":", 1)[1].split(",")]
            elif line.startswith("From:"):
                sender = line.split(":", 1)[1].strip()
            elif line.startswith("Attachment:"):
                file_attachment = "\n".join(lines[lines.index(line) + 1:])
                break
            else:
                message_body.append(line)

        if recipients and sender:
            # Encrypt the message body
            encrypted_message = aes_encrypt("\n".join(message_body).encode("utf-8"))
            
            # Store the message for each recipient
            for recipient in recipients:
                messages[recipient].append({"from": sender, "message": encrypted_message})
            
            # Handle file attachment if present
            if file_attachment:
                try:
                    decoded_file = base64.b64decode(file_attachment.encode('utf-8'))
                    for recipient in recipients:
                        file_path = f"/Users/andyxiao/PostGradProjects/CryptoGuardAI/{recipient}_attachment"
                        with open(file_path, 'wb') as file:
                            file.write(decoded_file)
                        print(f"File attachment saved to {file_path}")
                except Exception as e:
                    print(f"Error handling file attachment: {e}")    
            print(f"Encrypted Message for {recipients}: {encrypted_message}")
            print(f"Received email for {recipients}: {email_data}")
            client_socket.send(b"250 OK\n")
        else:
            client_socket.send(b"550 Missing recipient or sender\n")
    finally:
        client_socket.close()
def handle_pop3_client(client_socket):
    try:
        username = authenticate(client_socket)
        if not username:
            return
        client_socket.send(b"+OK POP3 server ready\n")
        recipient_address = client_socket.recv(1024).decode("utf-8").strip()
        print(f"Received POP3 request for: {recipient_address}")
        if recipient_address in messages and messages[recipient_address]:
            client_socket.send(f"+OK {len(messages[recipient_address])} messages\n".encode("utf-8"))
            for idx, msg in enumerate(messages[recipient_address], 1):
                decrypted_message = aes_decrypt(msg['message']).decode("utf-8")
                client_socket.send(f"{idx} {msg['from']} {len(msg['message'])}\n".encode("utf-8"))
                client_socket.send(f"{decrypted_message}\n".encode("utf-8"))
        else:
            client_socket.send(b"-ERR No messages\n")
    finally:
        client_socket.close()
#SMTP server receive messages
def start_server(port_smtp, port_pop3):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    #smtp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #smtp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #smtp_server = ssl.wrap_socket(
    context.load_cert_chain(
        #smtp_server,
        certfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt",
        keyfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.key"
        #server_side=True
    )
    #smtp_server.bind(('localhost',port_smtp))
    #smtp_server.listen(5)
    smtp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    smtp_server = context.wrap_socket(smtp_server, server_side=True)
    smtp_server.bind(('localhost', port_smtp))
    smtp_server.listen(5)
        

    pop3_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    pop3_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    pop3_server = context.wrap_socket(pop3_server, server_side=True)
    pop3_server.bind(('localhost', port_pop3))
    pop3_server.listen(5)
    print(f"Bob's SMTP server running on port {port_smtp}")
    print(f"Bob's POP3 server running on port {port_pop3}")
    #pop3_server = ssl.wrap_socket(
    #  certfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt",
    #    server_side=True
    #)
    while True:
        client_socket, _ = smtp_server.accept()
        threading.Thread(target = handle_smtp_client, args=(client_socket,)).start()

        client_socket, _ = pop3_server.accept()
        threading.Thread(target = handle_pop3_client, args=(client_socket,)).start()
         
        


if __name__ == "__main__":
    start_server(1026,1102)
