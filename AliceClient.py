"""
File: AliceClient_receive.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
"""

import socket

def send_email(recipient, sender, message_content, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', port))

    email_data = f"From: {sender}\nTo: {recipient}\n\n{message_content}"

    client_socket.send(email_data.encode("utf-8"))

    response = client_socket.recv(1024).decode("utf-8")
    print(response)

    client_socket.close()


if __name__ == "__main__":
    send_email("bob@example.com", "alice@example.com", "Hello Bob, this is Alice!", 1026)
