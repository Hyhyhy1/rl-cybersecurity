import socket
import logging
import time
import threading

import numpy as np
import gymnasium as gym

from gymnasium import spaces
from collections import defaultdict

""" from fixed_env.server import start_server
from fixed_env.message_generator import start_generator """

from server import start_server
from message_generator import start_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class TrafficEnv(gym.Env):
    def __init__(self, proxy_host='127.0.0.1', proxy_port=8080,
                    server_host='127.0.0.1', server_port=8090,
                    load_threshold=0.75, hazard_index=1):
        
        super(TrafficEnv).__init__()
        
        app_server = threading.Thread(target=start_server, daemon=True)
        app_server.start()

        self.wait_for_server(server_host, server_port)

        self.proxy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.proxy_server.bind((proxy_host, proxy_port))
        self.proxy_server.listen()

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.connect((server_host, server_port))


        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)

        self.state_data = np.zeros(5, dtype=np.float32)
        self.state_server = np.zeros(2, dtype=np.float32)


        self.load_threshold = load_threshold
        self.hazard_index = hazard_index

        self.request_buffer = [] # элемент массива (source ip, request, bool), true если пакет от нормального пользователя
        self.blocked_ips = set()

        self.current_data = None
        self.request_last_timestamp = defaultdict(int)
        self.request_size_data = defaultdict(int)
        self.request_count_data = defaultdict(int)
        self.request_delta_summ = defaultdict(int)


        logging.info(f"Прокси-сервер запущен на {proxy_host}:{proxy_port}")


    def wait_for_server(self, host, port, timeout=10):
            start = time.time()
            while time.time() - start < timeout:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((host, port))
                    s.close()
                    return
                except ConnectionRefusedError:
                    time.sleep(0.5)
                finally:
                    s.close()
            raise TimeoutError(f"Сервер приложения {host}:{port} не отвечает")


    def get_state(self):

        conn, addr = self.proxy_server.accept()

        with conn:
            
            logging.info(f'Подключение от {addr}')
            data = conn.recv(1024).decode('utf-8')
            current_time = time.time()
            data, addr, is_user = data.split('@@')
            self.current_data = data
            
            if data:

                msg_size = len(data.encode('utf-8'))#размер сообщения
                
                if addr not in self.request_size_data.keys():
                    self.request_size_data[addr] = msg_size
                    self.request_count_data[addr] = 1
                    self.request_last_timestamp[addr] = current_time
                    self.request_delta_summ[addr] = 0
                
                else:
                    self.request_size_data[addr] += msg_size
                    self.request_count_data[addr] += 1                    
                    self.request_delta_summ[addr] += current_time - self.request_last_timestamp[addr]
                    self.request_last_timestamp[addr] = current_time


                temp = self.request_count_data[addr] - 1 if self.request_count_data[addr] - 1 != 0 else 1

                all_msg_size = self.request_size_data[addr] #размер всех сообщений с адреса
                ave = self.request_delta_summ[addr] / temp #среднее время между запросами
                dev = (self.request_delta_summ[addr] - ave * temp) / temp #среднее отклонение от среднего времени между запросами
                req_count = self.request_count_data[addr] #число запросов с адреса
                
                self.state_data = np.array([msg_size, all_msg_size, ave, dev, req_count])
                
            else:
                self.state_data = np.zeros(5, np.float32)
            
        self.server.sendall(b'get metrics')
        server_data = self.server.recv(1024)
        cpu_usage, memory_usage = server_data.decode('utf-8').split(' ')
        print(cpu_usage, memory_usage)
        self.state_server = np.array([np.float32(cpu_usage), np.float32(memory_usage)])

        self.request_buffer.append((addr,np.hstack((self.state_data, self.state_server)), is_user == 'True'))
        
        return None


    def reset(self):

        start_generator()


        self.state_data = np.zeros(5, dtype=np.float32)
        self.state_server = np.zeros(2, dtype=np.float32)
        self.step_count = 0
        self.request_buffer = []

        for _ in range(100):
            self.get_state()
        
        print(f'Shape of request_buffer: {len(self.request_buffer)}')

        return self.request_buffer[0][1] #?
    

    def step(self, action):
        self.step_count += 1
        
        addr,_,is_user = self.request_buffer.pop(0)
        
        if action == 0:
            self.server.sendall(self.current_data.encode('utf-8'))

        elif action == 1:
            pass

        elif action == 2:
            self.blocked_ips.add(addr)

        #elif action == 3:
        #    request_source_block = self.features.get_netmask_from_ip(addr)
        #    self.blocked_ip_blocks.add(request_source_block)

        reward = self.get_reward(action, addr, is_user)
        state = self.request_buffer[0][1]
        done = self.step_count >= 1000
        info = {}
        

        return state, reward, done, info


    def get_server_usage(self):
        self.server.sendall(b'get server usage')
        data = self.server.recv(1024)
        cpu_usage, memory_usage, = data.decode('utf-8').split(' ')

        return np.float32(cpu_usage)/100, np.float32(memory_usage)/100
    

    def get_reward(self, action, addr, is_user):
        cpu_usage, memory_usage = self.get_server_usage()
        max_load = max(cpu_usage, memory_usage)
        is_heavy_loaded = max_load >= self.load_threshold
        
        
        reward = 0

        if is_heavy_loaded:
            if action != 3:
                if is_user == True and action == 0: #True negative
                    return reward
                
                elif is_user == True and (action == 1 or action == 2): #False Positive
                    reward = -2/(max_load / self.load_threshold * self.hazard_index)
                    return reward
                
                elif is_user == False and action == 0: #False Negative
                    reward = -(max_load / self.load_threshold * self.hazard_index)
                    return reward
                
                elif is_user == False and (action == 1 or action == 2): #True Positive
                    reward = max_load / self.load_threshold * self.hazard_index
                    return reward
                
                else:
                    return ValueError(f"Uncnown action: {action}")
                
            elif action == 3:
                if action == 3:
                    fp, tp = 0, 0
                    target_adress_group = self.features.get_netmask_from_ip(addr)
                    for i in range(1, len(self.request_buffer)):
                        if self.features.get_netmask_from_ip(self.request_buffer[i][0]) == target_adress_group:
                            if self.request_buffer[i][2] == True:
                                fp+=1

                            else:
                                tp+=1
                    
                    reward = (max_load / self.load_threshold * self.hazard_index) * tp - (2 / (max_load / self.load_threshold * self.hazard_index) * fp)
                    return reward

                else:
                    return ValueError(f"Uncnown action: {action}")
        
        else:
            if action != 3:
                if is_user == True and action == 0: #True negative
                    return reward
                
                elif is_user == True and (action == 1 or action == 2): #False Positive
                    reward = -2
                    return reward
                
                elif is_user == False and action == 1: #False Negative
                    reward = -1
                    return reward
                
                elif is_user == False and (action == 1 or action == 2): #True Positive
                    reward = 1
                    return reward
                
                else:
                    return ValueError(f"Uncnown action: {action}")
                
            elif action == 3:
                if action == 3:
                    fp, tp = 0, 0
                    target_adress_group = self.features.get_netmask_from_ip(addr)
                    for i in range(1, len(self.request_buffer)):
                        if self.features.get_netmask_from_ip(self.request_buffer[i][0]) == target_adress_group:
                            if self.request_buffer[i][2] == True:
                                fp+=1

                            else:
                                tp+=1
                    
                    reward = tp - 2 * fp
                    return reward

                else:
                    return ValueError(f"Uncnown action: {action}")


if __name__ == "__main__":

    env = TrafficEnv()
    state = env.reset()
    print(state)

    print(env.request_buffer[0])
