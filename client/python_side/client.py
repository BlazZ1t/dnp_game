import socket
import json
import threading
import time

# Server address (host, port)
SERVER_ADDR = ('10.247.1.236', 9999)
BUFFER_SIZE = 65536

LOCAL_ADDR = ('127.0.0.1', 9000)

shutdown = threading.Event()

def start_lua_listener(server_socket, lua_socket):
    def lua_listener():
        global LUA_ADDR
        LUA_ADDR = ''
        print('[Lua Listener] Waiting for lua client on ', LOCAL_ADDR)
        try:
            while not shutdown.is_set():
                data, addr = lua_socket.recvfrom(BUFFER_SIZE)
                #Get lua client address
                if not LUA_ADDR:
                    LUA_ADDR = addr
                    print('[Lua Listener] Got lua address: ', addr)
                if data:
                    msg = json.loads(data.decode('utf-8'))
                    #Resend the message to the server
                    if msg['action'] != 'leave':
                        server_socket.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)
                    #Leave if the message received
                    else:
                        server_socket.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)
                        shutdown.set()
                else:
                    print('[Lua Listener] Error: No data received')
        except Exception as e:
            print('[Lua Listener] Error: ', e)
    
    threading.Thread(target=lua_listener, daemon=True).start()
    
    
            


def start_server_listener(server_socket, lua_socket):
    def server_listener():
        try:
            while not shutdown.is_set():
                #Wait until lua client is connected and address is received
                if LUA_ADDR == '':
                    continue

                data, _ = server_socket.recvfrom(BUFFER_SIZE)
                if data:
                    msg = json.loads(data.decode('utf-8'))
                    if (LUA_ADDR == ''):
                        print('[Server Listener] But did not send it to the client')
                    else:
                        lua_socket.sendto(json.dumps(msg).encode('utf-8'), LUA_ADDR)
                else:
                    print('[Server Listener] Error: No data received')

        except Exception as e:
            print('[Server Listener] Error: ', e)

    threading.Thread(target=server_listener, daemon=True).start()


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.settimeout(1.0)
    lua_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    lua_socket.bind(LOCAL_ADDR)

    start_lua_listener(server_socket, lua_socket)
    start_server_listener(server_socket, lua_socket)

    while not shutdown.is_set():
        time.sleep(0)
    server_socket.close()
    lua_socket.close()


if __name__ == '__main__':
    main()
