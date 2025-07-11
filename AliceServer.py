"""
File: AliceServer.py
Author: Andy Xiao

Description:
SMTP and POP3 server for handling encrypted email communication for Alice.

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
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
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import time
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Message storage
try:
    primary_client = MongoClient("mongodb://localhost:27017,localhost:27018/?replicaSet=rs0")
    primary_db = primary_client["email_db"]
    primary_collection = primary_db["messages"]
    logging.info("Connected to primary MongoDB.")
except Exception as e:
    logging.error(f"Error connecting to primary MongoDB: {e}")
    exit(1)
try:
    backup_client = MongoClient("mongodb://localhost:27018/?replicaSet=rs0")
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
def log_user_action(user, action, details=""):
    """
    Logs user actions to the audit log.
    """
    logging.info(f"{datetime.utcnow()} | User: {user} | Action: {action} | Details: {details}")
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
        "deleted": False,
        "deleted_at": None,
        "retain_until": None
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
            logging.warning(f"{db['name']} database is unavailable. Skipping write.")
    synchronize_databases()

def mark_email_for_retention(email_id, retention_period_days):
    """
    Marks an email for retention by adding a retention period.
    """
    try:
        retention_date = datetime.utcnow() + timedelta(days=retention_period_days)
        result = primary_collection.update_one(
            {"_id": ObjectId(email_id)},
            {"$set": {"retention_date": retention_date}}
        )
        if result.modified_count > 0:
            logging.info(f"Email {email_id} marked for retention until {retention_date}.")
        else:
            logging.warning(f"No email found withID {email_id}.")
    except Exception as e:
        logging.error(f"Error marking email for retention: {e}")

def soft_delete_email(email_id, retention_time = 1):
    try:
        retention_until = datetime.utcnow() + timedelta(minutes=retention_time)
        for db in databases:
            result = db["collection"].update_one(
                {"_id": ObjectId(email_id)},
                {"$set": {
                    "deleted": True,
                    "deletion_date": datetime.utcnow(),
                    "retention_until": retention_until
                }}
            )
            if result.modified_count > 0:
                logging.info(f"Email {email_id} soft deleted in {db['name']} database.")
            else:
                logging.warning(f"Email {email_id} not found in {db['name']} database.")
    except Exception as e:
        logging.error(f"Error soft deleting email: {e}")
def hard_delete_email(email_id):
    try:
        now = datetime.utcnow()
        for db in databases:
            email = db["collection"].find_one({"_id": ObjectId(email_id)})
            if email:
                retention_until = email.get("retention_until")
                if retention_until and retention_until > now:
                    logging.info(f"Email {email_id} is still under retention until {retention_until}, skipping hard delete.")
                    continue
                result = db["collection"].delete_one({"_id": ObjectId(email_id)})
                if result.deleted_count > 0:
                    logging.info(f"email {email_id} deleted from {db['name']} database.")
                else:
                    logging.warning(f"Email {email_id} not found in {db['name']} database.")
            else:
                logging.warning(f"Email {email_id} not found in {db['name']} database.")
    except Exception as e:
        logging.error(f"error hard deleting email: {e}")
            
def enforce_retention_policy():
    try:
        now = datetime.utcnow()
        for db in databases:
            expired = db["collection"].find({
                "deleted": True,
                "retention_until": {"$lt": now}
            })
            for email in expired:
                db["collection"].delete_one({"_id": email["_id"]})
                logging.info(f"Email {email['_id']} permanently deleted due to retention policy.")
    except Exception as e:
        logging.error(f"Error enforcing retention policy: {e}") 
def handle_admin_commands():
    while True:
        command = input("Enter admin command: ")
        if command == "status":
            try:
                status = primary_client.admin.command("replSetGetStatus")
                print(json.dumps(status, indent=2, default=str))
            except Exception as e:
                print(f"Error fetching replica set status: {e}")
        if command == "check_consistency":
            check_database_consistency()
        elif command == "synchronize_all":
            synchronize_databases()
        elif command == "mark_retention":
            email_id = input("Enter email ID to retain: ")
            retention_days = int(input("Enter retention period in days: "))
            mark_email_for_retention(email_id, retention_days)
        elif command == "delete_email":
            email_id = input("Enter email ID to delete: ")
            soft_delete_email(email_id)
        elif command == "enforce_retention":
            enforce_retention_policy()
        elif command == "exit":
            break
def run_retention_enforcement(interval=60):  # Run every 24 hours
    while True:
        logging.info("Enforcing retention policy...")
        enforce_retention_policy()
        time.sleep(interval)
        
def synchronize_databases():
    try:
        now = datetime.utcnow()
        # Only synchronize if primary is healthy
        if not is_database_healthy(primary_client):
            logging.warning("Primary database is unavailable. Synchronization skipped.")
            return
        primary_ids = set(doc["_id"] for doc in primary_collection.find({},{"_id": 1}))
        backup_ids = set(doc["_id"] for doc in backup_collection.find({},{"_id": 1}))
        all_ids = primary_ids.union(backup_ids)
        for _id in all_ids:
            primary_doc = primary_collection.find_one({"_id": _id})
            backup_doc = backup_collection.find_one({"_id": _id})
            
            if primary_doc and not backup_doc:
                if not primary_doc.get("deleted") or (primary_doc.get("retention_until") and primary_doc["retention_until"] > now):
                    backup_collection.insert_one(primary_doc)
                    logging.info(f"Synchronized document with ID {_id} to backup database.")
                else:
                    primary_collection.delete_one({"_id": _id})
                    logging.info(f"Deleted document with ID {_id} from primary database (expired retention).")

            elif backup_doc and not primary_doc:
                if not backup_doc.get("deleted") or (backup_doc.get("retention_until") and backup_doc["retention_until"] > now):
                    primary_collection.insert_one(backup_doc)
                    logging.info(f"Synchronized document with ID {_id} to primary database.")
                else:
                    backup_collection.delete_one({"_id": _id})
                    logging.info(f"Hard deleted document with ID {_id} from backup database (expired retention).")
            elif primary_doc and backup_doc:
                if primary_doc != backup_doc:
                    primarytime = primary_doc.get("deletion_date") or primary_doc.get("timestamp")
                    backuptime = backup_doc.get("deletion_date") or backup_doc.get("timestamp")
                    if str(primarytime) > str(backuptime):
                        backup_collection.replace_one({"_id": _id}, primary_doc)
                        logging.info(f"Updated backup document with ID {_id} from primary database.")
                    else:
                        primary_collection.replace_one({"_id": _id}, backup_doc)
                        logging.info(f"Updated primary document with ID {_id} from backup database.")
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
                logging.info(f"Retrieved {len(messages)} messages for recipient: {recipient}")
                return messages
            else:
                logging.warning(f"No messages found for recipient: {recipient} in primary database.")
        except Exception as e:
            logging.error(f"Error retrieving messages from primary database: {e}")
    try:
        messages = list(backup_collection.find({"recipient": recipient}))
        if messages:
            logging.info(f"Retrieved {len(messages)} messages for recipient: {recipient} from backup database.")
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
        command = client_socket.recv(1024).decode("utf-8").strip()
        if command.startswith("DELETE"):
            parts = command.split(":")
            email_id = parts[1]
            retention_minutes = int(parts[2]) if len(parts) > 2 else 1
            soft_delete_email(email_id, retention_minutes)
            client_socket.send(b"+OK Email marked for deletion\n")
            return
        elif command.startswith("HARD_DELETE"):
            _, email_id = command.split(":", 1)
            email = primary_collection.find_one({"_id": ObjectId(email_id)})
            now = datetime.utcnow()
            if email and email.get("retention_until") and email["retention_until"] > now:
                client_socket.send(b"-ERR Email is under retention, cannot hard delete\n")
                logging.warning(f"Attempted to hard delete email {email_id} under retention.")
            else:
                hard_delete_email(email_id)
                client_socket.send(b"+OK Email permanently deleted\n")
            return
        elif command.startswith("RETAIN"):
            _, email_id, days = command.split(":")
            mark_email_for_retention(email_id, int(days))
            client_socket.send(b"+OK Email marked for retention\n")
            return
        elif command.startswith("EXPORT"):
            _, user_email = command.split(":", 1)
            emails = list(primary_collection.find({"recipient": user_email}))
            for email in emails:
                email["_id"] = str(email["_id"])
            data = json.dumps(emails).encode("utf-8 ")
            client_socket.sendall(data)
            client_socket.shutdown(socket.SHUT_WR)
            log_user_action(user_email, "EXPORT", f"User exported their data")
            return  
        else:
            recipient_address = command

    
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
    
    threading.Thread(target=start_smtp_server, args=(port_smtp, context), daemon=True).start()
    threading.Thread(target=start_pop3_server, args=(port_pop3, context), daemon=True).start()
    threading.Thread(target=run_periodic_synchronization, daemon=True).start()
    threading.Thread(target=run_retention_enforcement, daemon=True).start()
    threading.Thread(target=handle_admin_commands, daemon=True).start()
    logging.info(f"Server running on SMTP port {port_smtp} and POP3 port {port_pop3}")
    while True:
        pass
if __name__ == "__main__":
    start_server(1025, 1101)