"""
File: AliceClient_receive.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
"""

import socket


def receive_messages(recipient_email, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', port))

    client_socket.send(recipient_email.encode("utf-8"))
    response = client_socket.recv(1024).decode("utf-8")
    print(response)


    if "+OK" in response:
        while True:
            msg_info = client_socket.recv(1024).decode("utf-8")
            if not msg_info:
                break
            print(f"Email received: {msg_info}")
            message = client_socket.recv(4096).decode("utf-8")
            print(f"Message content: {message}")
    else:
        print("No emails to receive.")

    client_socket.close()

if __name__ == "__main__":
    receive_messages("bob@example.com", 1102)
