"""
File: AliceClient_receive.py
Author: Andy Xiao

Description:
Client for retrieving and decrypting emails from Alice's POP3 server.

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
"""

import socket
import ssl
import base64
import json
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from hmac_utils import generate_hmac

decrypted_emails = []

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
import os

def export_user_data(user_email, port):
    client_socket = None
    try:
        print("DEBUG: Starting export_user_data")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("DEBUG: Socket created")
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        print("DEBUG: Socket wrapped with SSL")
        client_socket.connect(('load_balancer', port))

        print("DEBUG: Connected to load_balancer")
        client_socket.recv(1024)  # Receive initial greeting
        print("DEBUG: Received initial greeting")
        client_socket.settimeout(5.0)
        command = f"EXPORT:{user_email}"
        command_bytes = command.encode('utf-8')
        hmac_value = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac_value.encode()
        client_socket.sendall(message)
        print("DEBUG: Sent EXPORT command")

        data = b""
        while True:
            try:
                print("DEBUG: Waiting to receive data chunk...")
                chunk = client_socket.recv(4096)
                print(f"DEBUG: Received chunk of length {len(chunk)}")
                if not chunk:
                    print("DEBUG: Received empty chunk, breaking loop")
                    break
                data += chunk
            except socket.timeout:
                print("DEBUG: Socket timeout, assuming end of data.")
                break

        print(f"DEBUG: Total data received: {len(data)}")
        print("DEBUG: /app/exports contents before write:", os.listdir("/app/exports"))
        export_path = f"/app/exports/{user_email}_export.json"
        with open(export_path, "wb") as f:
            f.write(data)
        print(f"User data exported to {export_path}")
        print("DEBUG: /app/exports contents after write:", os.listdir("/app/exports"))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_socket:
            client_socket.close()
def export_decrypted_emails():
    if decrypted_emails:
        for email in decrypted_emails:
            email.setdefault("from", "")
            email.setdefault("to", "")
            email.setdefault("timestamp", "")
            email.setdefault("subject", "")
            email.setdefault("message", "")
        export_path = "/app/exports/alice_decrypted_emails.json"
        with open(export_path, "w") as f:
            json.dump(decrypted_emails, f, indent=2)
        print(f"Decrypted emails exported to {export_path}")
        log_file = "/app/exports/userdata.log"
        with open(log_file, "a") as log_file:
            from datetime import datetime
            log_file.write(f"{datetime.now()} | User: {email['from']} | Action: export_decrypted_emails | Count: {len(decrypted_emails)}\n")
    else:
        print("No decrypted emails to export. Please receive messages first.")

def add_base64_padding(data):
    """
    Adds padding to Base64-encoded data if necessary.
    """
    return data + '=' * (-len(data) % 4)

def hybrid_decrypt(encrypted_aes_key, iv, encrypted_message, recipient_private_key_path):
    """
    Decrypts the message using hybrid decryption (RSA + AES).
    """
    try:
        # Decrypt the AES key using the recipient's private key (RSA)
        with open(recipient_private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(key_file.read(), password=None)

        if len(encrypted_aes_key) != 256:  # Assuming a 2048-bit RSA key
            raise ValueError("Invalid encrypted AES key size.")

        aes_key = private_key.decrypt(
            encrypted_aes_key,
            rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        # Decrypt the message using AES
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_padded_message = decryptor.update(encrypted_message) + decryptor.finalize()

        # Remove padding
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted_message = unpadder.update(decrypted_padded_message) + unpadder.finalize()

        return decrypted_message.decode("utf-8")
    except Exception as e:
        print(f"Decryption error: {e}")
        raise

def receive_messages(recipient_email, port):
    global decrypted_emails
    decrypted_emails = []
    client_socket = None
    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False        # ✅ FIRST: Disable hostname checking
        context.verify_mode = ssl.CERT_NONE  
        # Removed: 
    
        # Create and wrap the socket with SSL
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        client_socket.connect(('load_balancer', port))
        client_socket.settimeout(2.0)  # <-- Add this line

        # Send recipient email
        command_bytes = recipient_email.encode("utf-8")
        hmac_value = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac_value.encode()
        client_socket.sendall(message)
        # Receive server response
        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
        
        if "+OK" in response:
            while True:
                try:
                    # Receive metadata line
                    msg_info = client_socket.recv(1024).decode("utf-8").strip()
                    if not msg_info:
                        break
                except socket.timeout:
                    break
                try:
                    msg_info_dict = json.loads(msg_info)
                except Exception:
                    print("Error parsing metadata JSON.")
                    continue

                # Receive encrypted components
                raw_aes_key = client_socket.recv(4096).decode("utf-8").strip()
                raw_iv = client_socket.recv(1024).decode("utf-8").strip()
                raw_message = client_socket.recv(4096).decode("utf-8").strip()

                # Ensure no empty components
                if not raw_aes_key or not raw_iv or not raw_message:
                    print("Missing one or more components of the encrypted message.")
                    continue

                print(f"Raw AES key (Base64): {raw_aes_key}")
                print(f"Raw IV (Base64): {raw_iv}")
                print(f"Raw Message (Base64): {raw_message}")

                try:
                    encrypted_aes_key = base64.b64decode(add_base64_padding(raw_aes_key))
                    iv = base64.b64decode(add_base64_padding(raw_iv))
                    encrypted_message = base64.b64decode(add_base64_padding(raw_message))
                except Exception as decode_error:
                    print(f"Error decoding Base64 data: {decode_error}")
                    continue

                if len(encrypted_aes_key) != 256:
                    print(f"Invalid RSA-encrypted AES key size: {len(encrypted_aes_key)} bytes")
                    continue
                if len(iv) != 16:
                    print(f"Invalid IV size: {len(iv)} bytes")
                    continue

                try:
                    decrypted_message = hybrid_decrypt(
                        encrypted_aes_key, iv, encrypted_message, "/app/Alice_private_key.pem"
                    )
                    print(f"Decrypted message content: {decrypted_message}")
                    decrypted_emails.append({
                        "from": msg_info_dict.get("sender", ""),
                        "to": msg_info_dict.get("recipient", ""),
                        "timestamp": msg_info_dict.get("timestamp", ""),
                        "message": decrypted_message
                    })
                except Exception as decryption_error:
                    print(f"Error decrypting message: {decryption_error}")
                    continue  # Skip to the next message
        else:
            print("No emails to receive.")
    except ssl.SSLError as e:
        print(f"SSL error: {e}")
    except ConnectionError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client_socket:  # ✅ Only close if socket was created
            client_socket.close()
        
import ssl

def delete_email(email_id, port):
    client_socket = None
    try:
        context = ssl.create_default_context()
        context.check_hostname = False        # FIRST
        context.verify_mode = ssl.CERT_NONE   # SECOND
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        client_socket.connect(('load_balancer', port))
        client_socket.recv(1024)  # Receive initial greeting

        command = f"DELETE:{email_id}"
        command_bytes = command.encode('utf-8')
        hmac = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac.encode()
        client_socket.sendall(message)

        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
        with open("userdata.log", "a") as log_file:
            from datetime import datetime
            log_file.write(f"{datetime.now()} | Action: soft delete email | Email ID: {email_id}\n")
   
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_socket:
            client_socket.close()
def hard_delete_email(email_id, port):
    client_socket = None
    try:
        context = ssl.create_default_context()
        context.check_hostname = False        # FIRST
        context.verify_mode = ssl.CERT_NONE   # SECOND
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        client_socket.connect(('load_balancer', port))
        client_socket.recv(1024)

        command = f"HARD_DELETE:{email_id}"
        command_bytes = command.encode('utf-8')
        hmac = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac.encode()
        client_socket.sendall(message)

        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
        with open("userdata.log", "a") as log_file:
            from datetime import datetime
            log_file.write(f"{datetime.now()} | Action: hard delete email | Email ID: {email_id}\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_socket:
            client_socket.close()
def reverse_self_delete_email(email_id, port):
    client_socket = None
    try:
        context = ssl.create_default_context()
        context.check_hostname = False        # FIRST
        context.verify_mode = ssl.CERT_NONE   # SECOND
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        client_socket.connect(('load_balancer', port))
        client_socket.recv(1024)  # Receive initial greeting

        command = f"UNDELETE:{email_id}"
        command_bytes = command.encode("utf-8")
        hmac = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac.encode()
        client_socket.sendall(message)

        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
        with open("userdata.log", "a") as log_file:
            from datetime import datetime
            log_file.write(f"{datetime.now()} | Action: reverse self delete email | Email ID: {email_id}\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_socket:
            client_socket.close()

def retain_email(email_id, retention_days, port):
    client_socket = None
    try:
        context = ssl.create_default_context()
        context.check_hostname = False        # FIRST
        context.verify_mode = ssl.CERT_NONE   # SECOND
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='load_balancer')
        client_socket.connect(('load_balancer', port))
        client_socket.recv(1024)  # Receive initial greeting

        command = f"RETAIN:{email_id}:{retention_days}"
        command_bytes = command.encode('utf-8')
        hmac = generate_hmac(command_bytes)
        message = command_bytes + b'\n' + hmac.encode()
        client_socket.sendall(message)

        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
        with open("userdata.log", "a") as log_file:
            from datetime import datetime
            log_file.write(f"{datetime.now()} | Action: retain email | Email ID: {email_id} | Retention Days: {retention_days}\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_socket:
            client_socket.close()

def manage_emails_menu(port):
    while True:
        print("\nOptions:")
        print("1. Delete an email")
        print("2. Retain an email")
        print("3. Hard delete an email")
        print("4. Export my data")
        print("5. Export decrypted emails")
        print("6. Reverse soft delete")
        print("7. Exit")
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
            export_user_data("alice@example.com", port)
        elif choice == '5':
            export_decrypted_emails()
        elif choice == '6':
            email_id = input("Enter the email ID to reverse soft delete: ")
            reverse_self_delete_email(email_id, port)
        elif choice == '7':
            print("Exiting the menu.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    show_privacy_notice()
    receive_messages("alice@example.com", 2526)
    manage_emails_menu(2526)