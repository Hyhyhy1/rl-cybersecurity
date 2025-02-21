""" import socket
import logging
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor
from prometheus_client import Gauge

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

CPU_USAGE = Gauge('cpu_usage_percent', 'Current CPU usage in percent')
MEMORY_USAGE = Gauge('memory_usage_percent', 'Current memory usage in percent')

def update_system_metrics():
    CPU_USAGE.set(psutil.cpu_percent(interval=1))
    MEMORY_USAGE.set(psutil.virtual_memory().percent)

def handle_client(conn, addr):
    try:
        logging.info(f"Подключение от {addr}")

        with conn:
            data = conn.recv(1024)
            if not data:
                return

            decoded_data = data.decode('utf-8')
            logging.info(f"Получен пакет:\n{decoded_data}")

            if decoded_data.strip() == 'get state for features':
                response = f'{CPU_USAGE._value.get()} {MEMORY_USAGE._value.get()}'
            elif decoded_data.strip() == 'get server usage':
                response = f'{psutil.cpu_percent(interval=1)} {psutil.virtual_memory().percent}'
            else:
                response = "Invalid request"
                update_system_metrics()

            conn.sendall(response.encode('utf-8'))

    except Exception as e:
        logging.error(f"Ошибка обработки запроса: {e}")
    finally:
        logging.info(f"Соединение с {addr} закрыто")

def start_server(host='127.0.0.1', port=8090, memory_limit=512*1024*1024):
    process = psutil.Process()
    
    # Установка ограничений ресурсов
    if hasattr(process, 'rlimit'):
        process.rlimit(psutil.RLIMIT_AS, (memory_limit, memory_limit))
    process.cpu_affinity([0])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        logging.info(f"Сервер запущен на {host}:{port}")

        # Пул потоков с ограничением в 20 рабочих
        with ThreadPoolExecutor(max_workers=20) as executor:
            while True:
                conn, addr = s.accept()
                executor.submit(handle_client, conn, addr) """





import socket
import threading
import logging
import random

CPU_LOAD = 0.0
MEMORY_USAGE = 0.0

def update_metrics():
    pass

def handle_client(conn):
    while True:
        data = conn.recv(1024)

        if not data:
            break

        decoded_data = data.decode('utf-8')
        logging.info(f"Получен пакет:{decoded_data}")

        if decoded_data.strip() == 'get metrics':
            response = f"{CPU_LOAD} {MEMORY_USAGE}"
            
            conn.sendall(response.encode('utf-8'))
        else:
            update_metrics()


def start_server(host='127.0.0.1', port = 8090):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    logging.info(f"Сервер запущен на {host}:{port}")
    
    while True:
        client, _ = server.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()