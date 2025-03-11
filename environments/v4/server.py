import socket
import threading
import logging
import random

CPU_LOAD = 0.0
MEMORY_USAGE = 0.0

def update_metrics():
    CPU_LOAD, MEMORY_USAGE = random.randint(0,100), random.randint(0,100)


def handle_client(conn, logging_flag):
    while True:
        data = conn.recv(1024)

        if not data:
            break

        decoded_data = data.decode('utf-8')

        if logging_flag:
            logging.info(f"Получен пакет: {decoded_data}")

        if decoded_data.strip() == 'get metrics':
            response = f"{CPU_LOAD} {MEMORY_USAGE}"
            
            conn.sendall(response.encode('utf-8'))
        else:
            update_metrics()


def start_server(logging_flag=False, host='127.0.0.1', port = 8090):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    if logging_flag:
        logging.info(f"Сервер запущен на {host}:{port}")
    
    while True:
        client, _ = server.accept()
        threading.Thread(target=handle_client, args=(client, logging_flag), daemon=True).start()