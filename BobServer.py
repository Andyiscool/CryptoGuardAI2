"""
File: AliceClient_receive.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
"""

import socket
import threading
from collections import defaultdict

messages = defaultdict(list)

#send email
def handle_smtp_client(client_socket):
    try:
        client_socket.send(b"220 SMTP server ready\n")
        email_data = client_socket.recv(1024).decode("utf-8")
        lines = email_data.split('\n')
        recipient = None
        sender = None
        message_body = []

        for line in lines:
            if line.startswith("To:"):
                recipient = line.split(":",1)[1].strip()
            elif line.startswith("From:"):
                sender = line.split(":",1)[1].strip()
            else:
                message_body.append(line)

        if recipient and sender:
            messages[recipient].append({"from": sender, "message": "\n".join(message_body)})
            print(f"Received email for {recipient}: {email_data}")
            client_socket.send(b"250 OK\n")
        else:
            client_socket.send(b"550 Missing recipient or sender\n")
            
    finally:
        client_socket.close()

#receive email
def handle_pop3_client(client_socket):
    try:
        client_socket.send(b"+OK POP3 server ready\n")
        recipient_address = client_socket.recv(1024).decode("utf-8").strip()
        print(f"Received POP3 request for: {recipient_address}")
        if recipient_address in messages and messages[recipient_address]:
            client_socket.send(f"+OK {len(messages[recipient_address])} messages\n".encode("utf-8"))
            for idx, msg in enumerate(messages[recipient_address], 1):
                client_socket.send(f"{idx} {msg['from']} {len(msg['message'])}\n".encode("utf-8"))
                client_socket.send(f"{msg['message']}\n".encode("utf-8"))
        else:
            client_socket.send(b"-ERR No messages\n")
    finally:
        client_socket.close()
#SMTP server receive messages
def start_server(port_smtp, port_pop3):
    smtp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    smtp_server.bind(('localhost',port_smtp))
    smtp_server.listen(5)
        

    pop3_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    pop3_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    pop3_server.bind(('localhost', port_pop3))
    pop3_server.listen(5)
    print(f"Bob's SMTP server running on port {port_smtp}")
    print(f"Bob's POP3 server running on port {port_pop3}")
    while True:
        client_socket, _ = smtp_server.accept()
        threading.Thread(target = handle_smtp_client, args=(client_socket,)).start()

        client_socket, _ = pop3_server.accept()
        threading.Thread(target = handle_pop3_client, args=(client_socket,)).start()
         
        


if __name__ == "__main__":
    start_server(1026,1102)
