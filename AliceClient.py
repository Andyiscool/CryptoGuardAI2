"""
File: AliceClient.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""

import socket
import ssl
import base64
from user_management import register_user

def send_email(recipient, sender, password, message_content, port, file_path=None):
    context = ssl.create_default_context()
    context.load_verify_locations(cafile="/Users/andyxiao/PostGradProjects/CryptoGuardAI/server.crt")  # Path to the self-signed certificate

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket = context.wrap_socket(client_socket, server_hostname='localhost')

    try:
        client_socket.connect(('localhost', port))

        response = client_socket.recv(1024).decode("utf-8")
        print(response)
        client_socket.send(sender.encode("utf-8"))

        response = client_socket.recv(1024).decode("utf-8")
        print(response)
        client_socket.send(password.encode("utf-8"))

        response = client_socket.recv(1024).decode("utf-8")
        print(response)

        if "+OK" in response:
            # Ensure recipient is a list
            if isinstance(recipient, str):
                recipients = [recipient]
            else:
                recipients = recipient

            recipients_str = ", ".join(recipients)
            email_data = f"From: {sender}\nTo: {recipients_str}\n\n{message_content}"

            if file_path:
                try:
                    with open(file_path, 'rb') as file:
                        file_content = file.read()
                        encoded_file = base64.b64encode(file_content).decode('utf-8')
                        email_data += f"\n\nAttachment: {encoded_file}"
                        print(f"File {file_path} encoded and attached.")
                except FileNotFoundError:
                    print(f"Error: File {file_path} not found.")
                    return

            client_socket.send(email_data.encode("utf-8"))
            response = client_socket.recv(1024).decode("utf-8")
            print(response)
        else:
            print("Authentication failed.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()
def register():
    username = input("Enter your email address: ")
    password = input("Enter your password: ")
    confirm_password = input("Confirm your password: ")
    if password != confirm_password:
        print("Passwords do not match. Please try again.")
        return
    response = register_user(username, password)
    # Here you would typically save the user data to a database or a file
    print(response)
if __name__ == "__main__":
    send_email(
        recipient="bob@example.com",
        sender="alice@example.com",
        password="securepass",
        message_content="Hello Bob, this is Alice!",
        port=1026
    )
