"""
File: BobServer.py
Author: Andy Xiao

Description:
SMTP and POP3 server for handling encrypted email communication for Bob.

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
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Message storage
try:
    primary_client = MongoClient("mongodb://localhost:27017/")
    primary_db = primary_client["email_db"]
    primary_collection = primary_db["messages"]
    logging.info("Connected to primary MongoDB.")
except Exception as e:
    logging.error(f"Error connecting to primary MongoDB: {e}")
    exit(1)
try:
    backup_client = MongoClient("mongodb://localhost:27018/")
    backup_db = backup_client["email_db_backup"]
    backup_collection = backup_db["messages"]
    logging.info("Connected to backup MongoDB.")
except Exception as e:
    logging.error(f"Error connecting to backup MongoDB: {e}")
    exit(1)
databases = [
    {"name": "primary", "client": primary_client, "collection": primary_collection},
    {"name": "backup", "client": backup_client, "collection": backup_collection},
]
def is_database_healthy(client):
    try:
        client.admin.command('ping')
        return True
    except Exception as e:
        logging.error(f"Database health check failed: {e}")
        return False

def retry_operation(operation, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return operation()
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    logging.error("All retry attempts failed.")
    return None
def notify_admin(message):
    logging.error(f"ADMIN NOTIFICATION: {message}")
def check_database_consistency():
    primary_messages = list(primary_collection.find())
    backup_messages = list(backup_collection.find())
    if len(primary_messages) != len(backup_messages):
        logging.warning("Primary and backup databases are out of sync!")
def run_periodic_consistency_check(interval=300):
    while True:
        logging.info("Running periodic database consistency check...")
        check_database_consistency()
        time.sleep(interval)
def handle_admin_commands():
    while True:
        command = input("Enter admin command: ")
        if command == "check_consistency":
            check_database_consistency()
        elif command == "synchronize_all":
            synchronize_databases()
        elif command == "exit":
            break
def store_message_in_mongodb(recipient, sender, aes_key, iv, encrypted_message):
    message_data = {
        "recipient": recipient,
        "timestamp": datetime.utcnow().isoformat(),
        "sender": sender,
        "aes_key": base64.b64encode(aes_key).decode("utf-8"),
        "iv": base64.b64encode(iv).decode("utf-8"),
        "message": base64.b64encode(encrypted_message).decode("utf-8"),
    }
    for db in databases:
        if is_database_healthy(db["client"]):
            try:
                if not db["collection"].find_one({"_id": message_data.get("_id")}):
                    db["collection"].insert_one(message_data)
                    logging.info(f"Message stored in {db['name']} database.")
            except Exception as e:
                logging.error(f"Error storing message in {db['name']} database: {e}")
        else:
            logging.warning(f"{db['name']} database is not available. Skipping write.")
    synchronize_databases()

def synchronize_databases():
    try:
        for source_db in databases:
            if is_database_healthy(source_db["client"]):
                logging.info(f"Synchronizing from {source_db['name']} database...")
                source_messages = list(source_db["collection"].find())

                for target_db in databases:
                    if target_db["name"] != source_db["name"]:
                        if is_database_healthy(target_db["client"]):
                            for message in source_messages:
                                if not target_db["collection"].find_one({"_id": message["_id"]}):
                                    target_db["collection"].insert_one(message)
                                    logging.info(f"Synchronized message with ID {message['_id']} to {target_db['name']} database.")
                        else:
                            logging.warning(f"Target database {target_db['name']} is unavailable. Skipping synchronization.")
            else:
                logging.warning(f"Source database {source_db['name']} is unavailable. Skipping synchronization.")
    except Exception as e:
        logging.error(f"Error during synchronization: {e}")
    
def run_periodic_synchronization(interval=30):
    while True:
        logging.info("Running periodic database synchronization...")
        synchronize_databases()
        time.sleep(interval)

def retrieve_messages_from_mongodb(recipient):
    if is_database_healthy(primary_client):
        try:
            messages = list(primary_collection.find({"recipient": recipient}))
            if messages:
                logging.info(f"Retrieved {len(messages)} messages from primary database for recipient: {recipient}")
                return messages
            else:
                logging.warning(f"No messages found for recipient: {recipient} in primary database.")
        except Exception as e:
            logging.error(f"Error retrieving messages from primary database: {e}")
    try:
        messages = list(backup_collection.find({"recipient": recipient}))
        if messages:
            logging.info(f"Retrieved {len(messages)} messages from backup database for recipient: {recipient}")
            return messages
        else:
            logging.warning(f"No messages found for recipient: {recipient} in backup database.")
    except Exception as e:
        logging.error(f"Error retrieving messages from backup database: {e}")
    return []
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
def start_smtp_server(port_smtp, context):
    smtp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    smtp_server = context.wrap_socket(smtp_server, server_side=True)
    smtp_server.bind(('localhost', port_smtp))
    smtp_server.listen(5)
    logging.info(f"Alice's SMTP server running on port {port_smtp}")
    while True:
        client_socket, _ = smtp_server.accept()
        threading.Thread(target=handle_smtp_client, args=(client_socket,)).start()

def start_pop3_server(port_pop3, context):
    pop3_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    pop3_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    pop3_server = context.wrap_socket(pop3_server, server_side=True)
    pop3_server.bind(('localhost', port_pop3))
    pop3_server.listen(5)
    logging.info(f"Alice's POP3 server running on port {port_pop3}")
    while True:
        client_socket, _ = pop3_server.accept()
        threading.Thread(target=handle_pop3_client, args=(client_socket,)).start()

def start_server(port_smtp, port_pop3):
    """
    Starts the SMTP and POP3 servers.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        certfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt",
        keyfile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.key"
    )
    logging.info("Synchronizing all databases on startup...")
    synchronize_databases()
    logging.info("Checking database consistency...")

    threading.Thread(target=start_smtp_server, args=(port_smtp, context), daemon = True).start()

    threading.Thread(target=start_pop3_server, args=(port_pop3, context), daemon=True).start()
    threading.Thread(target=run_periodic_synchronization, daemon=True).start()
    threading.Thread(target=handle_admin_commands, daemon=True).start()
    logging.info(f"Alice server running")
    while True:
        pass
if __name__ == "__main__":
    start_server(1026, 1102)