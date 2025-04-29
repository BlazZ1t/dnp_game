import subprocess
import threading
import os
import sys
import time
import json
import socket

SERVER_ADDR = ('10.247.1.236', 9999)
BUFFER_SIZE = 65536
LOCAL_ADDR = ('127.0.0.1', 9000)
shutdown = threading.Event()
LUA_ADDR = ''

# ------------------------------------------------
# RESOURCE PATH FOR PYINSTALLER
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

# ------------------------------------------------
# LAUNCHER FUNCTIONS
def start_bridge():
    # Start a new copy of this exe with --bridge flag
    return subprocess.Popen([sys.executable, '--bridge'])

def start_game():
    exe_path = resource_path(os.path.join('Tetanki', 'Tetanki.exe'))
    return subprocess.Popen([exe_path], cwd=resource_path('Tetanki'))

# ------------------------------------------------
# BRIDGE LOGIC
def start_lua_listener(server_socket, lua_socket):
    def lua_listener():
        global LUA_ADDR
        print('[Lua Listener] Waiting for Lua client on', LOCAL_ADDR)
        try:
            while not shutdown.is_set():
                data, addr = lua_socket.recvfrom(BUFFER_SIZE)
                if not LUA_ADDR:
                    LUA_ADDR = addr
                    print('[Lua Listener] Got Lua address:', addr)
                if data:
                    msg = json.loads(data.decode('utf-8'))
                    if msg['action'] != 'leave':
                        server_socket.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)
                    else:
                        server_socket.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)
                        shutdown.set()
        except Exception as e:
            print('[Lua Listener] Error:', e)
    threading.Thread(target=lua_listener, daemon=True).start()

def start_server_listener(server_socket, lua_socket):
    def server_listener():
        try:
            while not shutdown.is_set():
                if LUA_ADDR == '':
                    continue
                data, _ = server_socket.recvfrom(BUFFER_SIZE)
                if data:
                    msg = json.loads(data.decode('utf-8'))
                    lua_socket.sendto(json.dumps(msg).encode('utf-8'), LUA_ADDR)
        except Exception as e:
            print('[Server Listener] Error:', e)
    threading.Thread(target=server_listener, daemon=True).start()

def run_bridge():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.settimeout(1.0)
    lua_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    lua_socket.bind(LOCAL_ADDR)

    start_lua_listener(server_socket, lua_socket)
    start_server_listener(server_socket, lua_socket)

    while not shutdown.is_set():
        time.sleep(0.1)

    server_socket.close()
    lua_socket.close()
    print('[Bridge] Shutting down.')

# ------------------------------------------------

def main():
    if '--bridge' in sys.argv:
        run_bridge()
    else:
        print('[Launcher] Starting bridge...')
        bridge_proc = start_bridge()
        time.sleep(1)
        print('[Launcher] Starting Lua game...')
        game_proc = start_game()
        game_proc.wait()
        print('[Launcher] Game exited.')

# ------------------------------------------------
if __name__ == '__main__':
    main()
