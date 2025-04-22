"""
File: load_balancer.py
Author: Andy Xiao

Description:
Balance the loads between multiple servers

References:
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""
import socket
import threading

smtp_servers = [("localhost", 1025), ("localhost", 1026)]
pop3_servers = [("localhost", 1101), ("localhost", 1102)]
smtp_current_server = 0
pop3_current_server = 0

def handle_client(client_socket, protocol):
    global smtp_current_server, pop3_current_server
    if protocol == "SMTP":
        server_host, server_port = smtp_servers[smtp_current_server]
        smtp_current_server = (smtp_current_server + 1) % len(smtp_servers)
    elif protocol == "POP3":
        server_host, server_port = pop3_servers[pop3_current_server]
        pop3_current_server = (pop3_current_server + 1) % len(pop3_servers)
    else:
        print("Unknown protocol")
        client_socket.close()
        return
    print(f"Forwarding request to server: {server_host}:{server_port}") 
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((server_host, server_port))
        threading.Thread(target=forward, args=(client_socket, server_socket)).start()
        threading.Thread(target=forward, args=(server_socket, client_socket)).start()
    except Exception as e:
        print(f"Error connecting to backend server: {e}")
        client_socket.close()
def forward(source, destination):
    try:
        while True:
            data = source.recv(4096)
            if not data:
                print("Connection closed by source.")

                break
            print(f"Forwarding data: {data.decode('utf-8', errors='replace')}")

            destination.sendall(data)
    except Exception as e:
        print(f"Error forwarding data: {e}")
    finally:
        source.close()
        destination.close()
def start_smtp_listener(smtp_port):
    smtp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    smtp_listener.bind(('localhost', smtp_port))
    smtp_listener.listen(5)
    print(f"SMTP Load balancer running on port {smtp_port}")

    while True:
        smtp_client_socket, smtp_client_address = smtp_listener.accept()
        print(f"Accepted SMTP connection from {smtp_client_address}")
        threading.Thread(target=handle_client, args=(smtp_client_socket, "SMTP")).start()

def start_pop3_listener(pop3_port):
    pop3_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    pop3_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    pop3_listener.bind(('localhost', pop3_port))
    pop3_listener.listen(5)
    print(f"POP3 Load balancer running on port {pop3_port}")

    while True:
        pop3_client_socket, pop3_client_address = pop3_listener.accept()
        print(f"Accepted POP3 connection from {pop3_client_address}")
        threading.Thread(target=handle_client, args=(pop3_client_socket, "POP3")).start()

def start_load_balancer(smtp_port, pop3_port):
    threading.Thread(target=start_smtp_listener, args=(smtp_port,), daemon=True).start()
    threading.Thread(target=start_pop3_listener, args=(pop3_port,), daemon=True).start()
    print("Load balancer is running...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down load balancer.")
if __name__ == "__main__":
    start_load_balancer(2525,2526)
