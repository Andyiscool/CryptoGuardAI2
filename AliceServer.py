"""
File: AliceServer.py
Author: Andy Xiao

Description:
SMTP and POP3 server for handling encrypted email communication for Alice.

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""

import socket
import ssl
import threading
from collections import defaultdict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import base64
import logging
from pymongo import MongoClient
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Message storage
client = MongoClient("mongodb://localhost:27017/")
db = client["email_db"]
collection = db["messages"]

def store_message_in_mongodb(recipient, sender, aes_key, iv, encrypted_message):
    collection.insert_one({
        "recipient": recipient,
        "timestamp": datetime.utcnow().isoformat(),
        "sender": sender,
        "aes_key": base64.b64encode(aes_key).decode("utf-8"),
        "iv": base64.b64encode(iv).decode("utf-8"),
        "message": base64.b64encode(encrypted_message).decode("utf-8"),
    })

def retrieve_messages_from_mongodb(recipient):
    return list(collection.find({"recipient": recipient}))
def handle_smtp_client(client_socket):
    """
    Handles SMTP client connections for sending emails.
    """
    try:
        client_socket.send(b"220 SMTP server ready\n")
        email_data = client_socket.recv(4096)
        logging.info(f"Raw email data received:\n{email_data.decode('utf-8', errors='replace')}")

        # Parse email data
        lines = email_data.split(b'\n')
        recipients = []
        sender = None
        encrypted_aes_key = None
        iv = None
        encrypted_message = None

        for line in lines:
            if line.startswith(b"To:"):
                recipients = [recipient.strip().decode("utf-8") for recipient in line.split(b":", 1)[1].split(b",")]
            elif line.startswith(b"From:"):
                sender = line.split(b":", 1)[1].strip().decode("utf-8")
            elif line.startswith(b"Encrypted-AES-Key:"):
                encrypted_aes_key = base64.b64decode(line.split(b":", 1)[1].strip()) 
            elif line.startswith(b"IV:"):
                iv = base64.b64decode(line.split(b":", 1)[1].strip())
            elif line.startswith(b"Message:"):
                encrypted_message = base64.b64decode(line.split(b":", 1)[1].strip())

        if recipients and sender and encrypted_aes_key and iv and encrypted_message:
            for recipient in recipients:
                store_message_in_mongodb(recipient, sender, encrypted_aes_key, iv, encrypted_message)
            client_socket.send(b"250 OK\n")
            logging.info(f"Message stored for recipients: {recipients}")
        else:
            client_socket.send(b"550 Missing recipient or sender\n")
            logging.warning("Missing recipient or sender in email data.")
    except Exception as e:
        logging.error(f"Error handling SMTP client: {e}")
    finally:
        client_socket.close()

def handle_pop3_client(client_socket):
    """
    Handles POP3 client connections for retrieving emails.
    """
    try:
        client_socket.send(b"+OK POP3 server ready\n")
        recipient_address = client_socket.recv(1024).decode("utf-8").strip()
        logging.info(f"Received POP3 request for: {recipient_address}")

        messages = retrieve_messages_from_mongodb(recipient_address)
        if messages:
            client_socket.send(f"+OK {len(messages)} messages\n".encode("utf-8"))
            for msg in messages:
                # Send encrypted components
                client_socket.send(base64.b64encode(base64.b64decode(msg["aes_key"])) + b"\n")
                client_socket.send(base64.b64encode(base64.b64decode(msg["iv"])) + b"\n")
                client_socket.send(base64.b64encode(base64.b64decode(msg["message"])) + b"\n")
                logging.info(f"Sent message to {recipient_address}")
        else:
            client_socket.send(b"-ERR No messages for this recipient\n")
            logging.warning(f"No messages found for recipient: {recipient_address}")
    except Exception as e:
        logging.error(f"Error handling POP3 client: {e}")
    finally:
        client_socket.close()
def start_server(port_smtp, port_pop3):
    """
    Starts the SMTP and POP3 servers.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        certfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt",
        keyfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.key"
    )

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

    logging.info(f"Alice's SMTP server running on port {port_smtp}")
    logging.info(f"Alice's POP3 server running on port {port_pop3}")

    while True:
        client_socket, _ = smtp_server.accept()
        threading.Thread(target=handle_smtp_client, args=(client_socket,)).start()

        client_socket, _ = pop3_server.accept()
        threading.Thread(target=handle_pop3_client, args=(client_socket,)).start()

if __name__ == "__main__":
    start_server(1025, 1101)