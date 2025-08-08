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
import sys
import os
from collections import defaultdict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import base64
import logging
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from hmac_utils import verify_hmac
import time
import json
import hashlib


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# FIX 1: Use environment variables for MongoDB connection
mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://mongo_primary:27017,mongo_backup:27017/?replicaSet=rs0')
logging.info(f"Connecting to MongoDB with URI: {mongodb_uri}")

# Message storage
try:
    primary_client = MongoClient(mongodb_uri)
    primary_db = primary_client["email_db"]
    primary_collection = primary_db["messages"]
    logging.info("Connected to primary MongoDB.")
except Exception as e:
    logging.error(f"Error connecting to primary MongoDB: {e}")
    # Don't exit, continue with backup only
    primary_client = None
    primary_db = None
    primary_collection = None

try:
    backup_client = MongoClient(mongodb_uri)
    backup_db = backup_client["email_db_backup"]
    backup_collection = backup_db["messages"]
    logging.info("Connected to backup MongoDB.")
except Exception as e:
    logging.error(f"Error connecting to backup MongoDB: {e}")
    backup_client = None
    backup_db = None
    backup_collection = None

# Only include available databases
databases = []
if primary_client is not None and primary_collection is not None:
    databases.append({"name": "primary", "client": primary_client, "collection": primary_collection})
if backup_client is not None and backup_collection is not None:
    databases.append({"name": "backup", "client": backup_client, "collection": backup_collection})

def log_user_action(user, action, details=""):
    """
    Logs user actions to the audit log.
    """
    logging.info(f"{datetime.utcnow()} | User: {user} | Action: {action} | Details: {details}")

def is_database_healthy(client):
    if not client:
        return False
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
    if primary_collection is None or backup_collection is None:
        logging.warning("Cannot check consistency - missing database connections")
        return
    
    primary_messages = list(primary_collection.find())
    backup_messages = list(backup_collection.find())
    if len(primary_messages) != len(backup_messages):
        logging.warning("Primary and backup databases are out of sync!")

def run_periodic_consistency_check(interval=300):
    while True:
        logging.info("Running periodic database consistency check...")
        check_database_consistency()
        time.sleep(interval)

# FIX 2: Handle Docker environment for admin commands
def handle_admin_commands():
    """
    Handle admin commands - disable in Docker non-interactive mode
    """
    # Check if running in Docker (no TTY)
    if not sys.stdin.isatty():
        logging.info("Running in non-interactive mode (Docker), admin commands disabled.")
        return
    
    while True:
        try:
            command = input("Enter admin command: ")
            if command == "status":
                try:
                    if primary_client:
                        status = primary_client.admin.command("replSetGetStatus")
                        print(json.dumps(status, indent=2, default=str))
                    else:
                        print("Primary client not available")
                except Exception as e:
                    print(f"Error fetching replica set status: {e}")
            elif command == "check_consistency":
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
        except EOFError:
            logging.info("Admin command input closed.")
            break
        except Exception as e:
            logging.error(f"Error in admin command: {e}")

def store_message_in_mongodb(recipient, sender, aes_key, iv, encrypted_message):
    # Create a deterministic ID based on message content
    message_hash = hashlib.sha256(
        recipient.encode() + sender.encode() + aes_key + iv + encrypted_message
    ).hexdigest()
    message_id = ObjectId(message_hash[:24])  # ObjectId needs 24 hex chars

    message_data = {
        "_id": message_id,
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

    stored_count = 0
    for db in databases:
        if is_database_healthy(db["client"]):
            try:
                # Use upsert to avoid duplicate insertions
                db["collection"].update_one(
                    {"_id": message_id},
                    {"$setOnInsert": message_data},
                    upsert=True
                )
                logging.info(f"Message stored in {db['name']} database.")
                stored_count += 1
            except Exception as e:
                logging.error(f"Error storing message in {db['name']} database: {e}")
        else:
            logging.warning(f"{db['name']} database is unavailable. Skipping write.")

    if stored_count > 0:
        synchronize_databases()
    else:
        logging.error("Failed to store message in any database!")

def mark_email_for_retention(email_id, retention_period_days):
    """
    Marks an email for retention by adding a retention period.
    """
    retention_date = datetime.utcnow() + timedelta(days=retention_period_days)
    updated = False
    for db in databases:
        if is_database_healthy(db["client"]):
            result = db["collection"].update_one(
                {"_id": ObjectId(email_id)},
                {"$set": {"retention_until": retention_date}}
            )
            if result.modified_count > 0:
                logging.info(f"Email {email_id} marked for retention until {retention_date} in {db['name']} database.")
                updated = True
    if not updated:
        logging.warning(f"Email {email_id} not found in any database.")
        
def soft_delete_email(email_id, retention_time=1):
    try:
        retention_until = datetime.utcnow() + timedelta(minutes=retention_time)
        for db in databases:
            if is_database_healthy(db["client"]):
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
            if is_database_healthy(db["client"]):
                email = db["collection"].find_one({"_id": ObjectId(email_id)})
                if email:
                    retention_until = email.get("retention_until")
                    if retention_until and retention_until > now:
                        logging.info(f"Email {email_id} is still under retention until {retention_until}, skipping hard delete.")
                        continue
                    result = db["collection"].delete_one({"_id": ObjectId(email_id)})
                    if result.deleted_count > 0:
                        logging.info(f"Email {email_id} deleted from {db['name']} database.")
                    else:
                        logging.warning(f"Email {email_id} not found in {db['name']} database.")
                else:
                    logging.warning(f"Email {email_id} not found in {db['name']} database.")
    except Exception as e:
        logging.error(f"Error hard deleting email: {e}")

def enforce_retention_policy():
    try:
        now = datetime.utcnow()
        for db in databases:
            if is_database_healthy(db["client"]):
                expired = db["collection"].find({
                    "deleted": True,
                    "retention_until": {"$lt": now}
                })
                for email in expired:
                    db["collection"].delete_one({"_id": email["_id"]})
                    logging.info(f"Email {email['_id']} permanently deleted due to retention policy.")
    except Exception as e:
        logging.error(f"Error enforcing retention policy: {e}")

def run_retention_enforcement(interval=60):
    while True:
        logging.info("Enforcing retention policy...")
        enforce_retention_policy()
        time.sleep(interval)

def synchronize_databases():
    try:
        now = datetime.utcnow()
        
        # Skip if we don't have both databases
        if primary_collection is None or backup_collection is None:
            logging.warning("Cannot synchronize - missing database connections")
            return
            
        # Only synchronize if primary is healthy
        if not is_database_healthy(primary_client):
            logging.warning("Primary database is unavailable. Synchronization skipped.")
            return

        primary_ids = set(doc["_id"] for doc in primary_collection.find({}, {"_id": 1}))
        backup_ids = set(doc["_id"] for doc in backup_collection.find({}, {"_id": 1}))
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
    # Try primary first if available
    if primary_collection is not None and is_database_healthy(primary_client):
        try:
            messages = list(primary_collection.find({"recipient": recipient}))
            if messages:
                logging.info(f"Retrieved {len(messages)} messages for recipient: {recipient}")
                return messages
            else:
                logging.warning(f"No messages found for recipient: {recipient} in primary database.")
        except Exception as e:
            logging.error(f"Error retrieving messages from primary database: {e}")
    
    # Try backup if primary failed or unavailable
    if backup_collection is not None:
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
        received_hmac = lines[-1].decode().strip()
        message_bytes = b'\n'.join(lines[:-1])
        if not verify_hmac(message_bytes, received_hmac):
            client_socket.send(b"550 HMAC verification failed\n")
            logging.warning("HMAC verification failed for incoming email.")
            return
        logging.info("HMAC verification succeeded.")
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
        data = client_socket.recv(1024)
        if b'\n' not in data:
            client_socket.send(b"-ERR Invalid command format\n")
            logging.error("Invalid command format received from client.")
            return
        command_bytes, received_hmac = data.rsplit(b'\n', 1)
        received_hmac = received_hmac.decode().strip()
        if not verify_hmac(command_bytes, received_hmac):
            client_socket.send(b"-ERR Invalid HMAC\n")
            logging.error("Invalid HMAC received from client.")
            return
        command = command_bytes.decode("utf-8").strip()
        
        if command.startswith("DELETE"):
            parts = command.split(":")
            email_id = parts[1]
            retention_minutes = int(parts[2]) if len(parts) > 2 else 1
            soft_delete_email(email_id, retention_minutes)
            client_socket.send(b"+OK Email marked for deletion\n")
            return
        elif command.startswith("HARD_DELETE"):
            _, email_id = command.split(":", 1)
            if primary_collection is not None:
                email = primary_collection.find_one({"_id": ObjectId(email_id)})
                now = datetime.utcnow()
                if email and email.get("retention_until") and email["retention_until"] > now:
                    client_socket.send(b"-ERR Email is under retention, cannot hard delete\n")
                    logging.warning(f"Attempted to hard delete email {email_id} under retention.")
                else:
                    hard_delete_email(email_id)
                    client_socket.send(b"+OK Email permanently deleted\n")
            else:
                client_socket.send(b"-ERR Database unavailable\n")
            return
        elif command.startswith("UNDELETE"):
            email_id = command.split(":", 1)[1].strip()
            updated = False
            for db in databases:
                if is_database_healthy(db["client"]):
                    result = db["collection"].update_one(
                        {"_id": ObjectId(email_id)},
                        {"$set": {
                            "deleted": False,
                            "deleted_at": None,
                            "retention_until": None,
                            "deletion_date": None
                        }}
                    )
                    if result.modified_count > 0:
                        updated = True
            if updated:
                client_socket.send(b"+OK Email restored from soft delete\n")
            else:
                client_socket.sendall(b"Email not found or not deleted\n")
        elif command.startswith("RETAIN"):
            _, email_id, days = command.split(":")
            mark_email_for_retention(email_id, int(days))
            client_socket.send(b"+OK Email marked for retention\n")
            return
        elif command.startswith("EXPORT"):
            _, user_email = command.split(":", 1)
            all_emails = []
            
            # Export from primary
            if primary_collection is not None and is_database_healthy(primary_client):
                try:
                    primary_emails = list(primary_collection.find({
                        "$or": [
                            {"recipient": user_email},
                            {"sender": user_email}
                        ]
                    }))
                    all_emails.extend(primary_emails)
                    logging.info(f"Exported {len(primary_emails)} emails from primary database for user {user_email}.")
                except Exception as e:
                    logging.error(f"Error exporting emails from primary database: {e}")
            
            # Export from backup
            if backup_collection is not None and is_database_healthy(backup_client):
                try:
                    backup_emails = list(backup_collection.find({
                        "$or": [
                            {"recipient": user_email},
                            {"sender": user_email}
                        ]
                    }))
                    existing_ids = {str(email["_id"]) for email in all_emails}
                    for email in backup_emails:
                        if str(email.get("_id", "")) not in existing_ids:
                            all_emails.append(email)
                    logging.info(f"Exported {len(backup_emails)} emails from backup database for user {user_email}.")
                except Exception as e:
                    logging.error(f"Error exporting emails from backup database: {e}")
            
            # Convert ObjectId to string
            for email in all_emails:
                email["_id"] = str(email["_id"])
            
            response_data = json.dumps(all_emails, indent=2, default=str)
            client_socket.sendall(response_data.encode("utf-8"))
            client_socket.shutdown(socket.SHUT_WR)
            logging.info(f"Exported {len(all_emails)} emails for user {user_email}.")
            log_user_action(user_email, "EXPORT", f"User exported their data")
            return
        else:
            recipient_address = command
            logging.info(f"Received POP3 request for: {recipient_address}")

            messages = retrieve_messages_from_mongodb(recipient_address)
            if messages:
                client_socket.send(f"+OK {len(messages)} messages\n".encode("utf-8"))
                for msg in messages:
                    # Send metadata as JSON
                    metadata = {
                        "sender": msg.get("sender", ""),
                        "recipient": msg.get("recipient", ""),
                        "timestamp": msg.get("timestamp", ""),
                        "_id": str(msg.get("_id", "")),
                        "deleted": msg.get("deleted", False),
                        "retain_until": str(msg.get("retain_until", "")),
                    }
                    client_socket.send((json.dumps(metadata) + "\n").encode("utf-8"))
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

# FIX 3: Bind to all interfaces (0.0.0.0) for Docker
def start_smtp_server(port_smtp, context):
    smtp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    smtp_server = context.wrap_socket(smtp_server, server_side=True)
    smtp_server.bind(('0.0.0.0', port_smtp))  # Changed from localhost to 0.0.0.0
    smtp_server.listen(5)
    logging.info(f"Alice's SMTP server running on port {port_smtp}")
    while True:
        client_socket, _ = smtp_server.accept()
        threading.Thread(target=handle_smtp_client, args=(client_socket,)).start()

def start_pop3_server(port_pop3, context):
    pop3_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    pop3_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    pop3_server = context.wrap_socket(pop3_server, server_side=True)
    pop3_server.bind(('0.0.0.0', port_pop3))  # Changed from localhost to 0.0.0.0
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
        certfile="server.crt",
        keyfile="server.key"
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
    
    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Server shutting down...")

if __name__ == "__main__":
    start_server(1025, 1101)