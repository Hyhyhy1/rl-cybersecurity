import socket
import string
import random
import time
import threading

def generate_message():
    symbols = string.ascii_letters + string.digits
    ip = ".".join(str(random.randint(1, 255)) for _ in range(4))
    temp = random.random()
    is_user = temp < 0.35

    message_length = random.randint(1, 30) if is_user else random.randint(1, 5)
    message = ''.join(random.choice(symbols) for _ in range(message_length))

    message = f'{message}@@{ip}@@{is_user}'

    return message.encode()


def send_messages(proxy_host='127.0.0.1', proxy_port=8080):
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((proxy_host, proxy_port))
                while True:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.sendall(generate_message())
                    time.sleep(random.uniform(0.1, 0.5))

        except Exception as e:
            pass
#            print(f"Connection error: {e}, retrying...")
#            time.sleep(1)

def start_generator():
    thread = threading.Thread(target=send_messages, daemon=True)
    thread.start()