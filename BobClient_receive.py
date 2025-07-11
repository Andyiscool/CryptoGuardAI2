"""
File: BobClient_receive.py
Author: Andy Xiao

Description:
Client for retrieving and decrypting emails from Bob's POP3 server.

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
def export_user_data(user_email, port):
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='localhost')
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)  # Receive initial greeting
        
        # Send request for user data
        command = f"EXPORT:{user_email}\n"
        client_socket.sendall(command.encode("utf-8"))
        
        data = b""
        while True:
           chunk = client_socket.recv(4096)
           if not chunk:
               break
           data += chunk
        
        with open(f"{user_email}_export.json", "wb") as f:
            f.write(data)
        print(f"User data exported to {user_email}_export.json")
    except Exception as e:
        print(f"Error exporting user data: {e}")
    finally:
        client_socket.close()

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
    """
    Connects to the POP3 server, authenticates, and retrieves encrypted emails.
    Decrypts the emails using the recipient's private key.
    """
    global decrypted_emails
    decrypted_emails = []
    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
    
        # Create and wrap the socket with SSL
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='localhost')
        client_socket.connect(('localhost', port))

        # Send recipient email
        client_socket.send(recipient_email.encode("utf-8"))

        # Receive server response
        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")

        if "+OK" in response:
            # Start retrieving messages
            while True:
                # Receive message metadata
                msg_info = client_socket.recv(1024).decode("utf-8").strip()
                if not msg_info:
                    break
                print(f"Email received: {msg_info}")

                try:
                    msg_info_dict = json.loads(msg_info)
                except Exception:
                    msg_info_dict = {"info": msg_info}
                # Receive and parse the encrypted message components
                raw_aes_key = client_socket.recv(4096).decode("utf-8").strip()
                raw_iv = client_socket.recv(1024).decode("utf-8").strip()
                raw_message = client_socket.recv(4096).decode("utf-8").strip()

                # Ensure no empty components
                if not raw_aes_key or not raw_iv or not raw_message:
                    print("Missing one or more components of the encrypted message.")
                    continue  # Skip to the next message

                # Debug received data
                print(f"Raw AES key (Base64): {raw_aes_key}")
                print(f"Raw IV (Base64): {raw_iv}")
                print(f"Raw Message (Base64): {raw_message}")

                # Decode and validate the components
                try:
                    encrypted_aes_key = base64.b64decode(add_base64_padding(raw_aes_key))
                    iv = base64.b64decode(add_base64_padding(raw_iv))
                    encrypted_message = base64.b64decode(add_base64_padding(raw_message))
                except Exception as decode_error:
                    print(f"Error decoding Base64 data: {decode_error}")
                    continue  # Skip to the next message

                # Validate AES key and IV sizes
                if len(encrypted_aes_key) != 256:  # RSA-encrypted AES key size
                    print(f"Invalid RSA-encrypted AES key size: {len(encrypted_aes_key)} bytes")
                    continue  # Skip to the next message

                if len(iv) != 16:  # 128-bit IV for AES
                    print(f"Invalid IV size: {len(iv)} bytes")
                    continue  # Skip to the next message

                try:
                    decrypted_message = hybrid_decrypt(
                        encrypted_aes_key, iv, encrypted_message, "/Users/andyxiao/PostGradProjects/CryptoGuardAI/Bob_private_key.pem"
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
        client_socket.close()
        
import ssl
def export_decrypted_emails():
    if decrypted_emails:
        with open("bob_decrypted_emails.json", "w") as f:
            json.dump(decrypted_emails, f, indent=2)
        print("Decrypted emails exported to bob_decrypted_emails.json")
    else:
        print("No decrypted emails to export. Please receive messages first.")
def delete_email(email_id, port):
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket = context.wrap_socket(client_socket, server_hostname='localhost')
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)  # Receive initial greeting
        command = f"DELETE:{email_id}\n"
        client_socket.sendall(command.encode("utf-8"))
        response = client_socket.recv(1024).decode("utf-8")
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
        client_socket = context.wrap_socket(client_socket, server_hostname='localhost')
        client_socket.connect(('localhost', port))
        client_socket.recv(1024)  # Receive initial greeting
        command = f"RETAIN:{email_id}:{retention_days}\n"
        client_socket.sendall(command.encode("utf-8"))
        response = client_socket.recv(1024).decode("utf-8")
        print(f"Server response: {response}")
    except Exception as e:
        print(f"Error sending retention request: {e}")
    finally:
        client_socket.close()

def manage_emails_menu(port):
    while True:
        print("\nOptions:")
        print("1. Delete an email")
        print("2. Retain an email")
        print("3. Hard delete an email")
        print("4. Export my data")
        print("5. Export decrypted emails")
        print("6. Exit")
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
            print("Export my data")
            export_user_data("bob@example.com", port)
        elif choice == '5':
            export_decrypted_emails()
        elif choice == '6':
            print("Exiting the menu.")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    show_privacy_notice()
    receive_messages("bob@example.com", 2526)
    manage_emails_menu(2526)