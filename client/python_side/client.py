import socket
import json
import threading
import time

# Server address (host, port)
SERVER_ADDR = ('127.0.0.1', 9999)
BUFFER_SIZE = 65536

# Lua interconnection (local)
LUA_INCOMING_ADDR = ('127.0.0.1', 9000)
LUA_OUTCOMING_ADDR = ('127.0.0.1', 9001)

#Shutdown all threads and the python script when the lua game quits
shutdown = threading.Event()

# Predefined commands with their required params
COMMANDS = [
    {"name": "Join Room",   "action": "join_room",  "params": []},
    {"name": "Set Ready",   "action": "set_ready",  "params": []},
    {"name": "Start Game",  "action": "start_game", "params": []},
    {"name": "Move",        "action": "move",       "params": ["x", "y", "direction"]},
    {"name": "Shoot",       "action": "shoot",      "params": []},
    {"name": "Chat",        "action": "chat",       "params": ["message"]},
    {"name": "Leave Game",  "action": "leave",      "params": []},
    {"name": "Custom JSON", "action": None,         "params": None},
]

def start_lua_bridge(server_sock):
    lua_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    lua_sock.bind(LUA_INCOMING_ADDR)

    print(f'[Lua Bridge] Listening for lua on {LUA_OUTCOMING_ADDR[1]}')
    def lua_listener():
        nonlocal player_id
        while not shutdown.is_set():
            try:
                data, addr = lua_sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode())
                print(msg)
                if msg['action'] == 'leave':
                    server_sock.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)

                if msg['action'] == 'join_room':
                    player_id = msg['player_id']
                    print(f'[Lua Bridge] Got player_id: {player_id}')
                    server_sock.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)

            except Exception as e:
                print('[Lua Listener Error] ', e)
        
        lua_sock.close()
        print('[Lua Bridge] Lua socket closed')
    
    player_id = None
    threading.Thread(target=lua_listener, daemon=True).start()
    while not player_id and not shutdown.is_set():
        time.sleep(0.1)
    return player_id


# WILL BE DONE IN LUA
# def build_message(cmd, player_id):
#     """
#     Build a JSON message dict based on the selected command.
#     For Custom JSON, prompts raw JSON input.
#     """
#     if cmd["action"] is None:
#         raw = input("Enter full JSON: ").strip()
#         try:
#             return json.loads(raw)
#         except json.JSONDecodeError:
#             print("Invalid JSON.")
#             return None

#     msg = {"action": cmd["action"], "player_id": player_id}

#     # gather additional params if needed
#     if cmd["params"]:
#         if cmd["action"] == "move":
#             # ask for x, y, direction
#             x = input("  x = ").strip()
#             y = input("  y = ").strip()
#             dir_ = input("  direction (up/down/left/right) = ").strip()
#             # convert to numbers if possible
#             msg["position"] = {
#                 "x": int(x) if x.isdigit() else float(x),
#                 "y": int(y) if y.isdigit() else float(y)
#             }
#             msg["direction"] = dir_
#         elif cmd["action"] == "chat":
#             text = input("  message = ").strip()
#             msg["message"] = text

#     return msg

def start_server_listener(server_sock, player_id):

    def listen():
        """
        Background thread: receive messages from server,
        auto-reply to 'ping' with 'pong', ignore printing pings.
        """
        while not shutdown.is_set():
            try:
                data, _ = server_sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode('utf-8'))

                action = msg.get('action')
                # auto-reply to ping silently
                if action == 'ping':
                    pong = {'action': 'pong', 'player_id': player_id}
                    server_sock.sendto(json.dumps(pong).encode('utf-8'), SERVER_ADDR)
                    continue

                udp_to_lua = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_to_lua.sendto(json.dumps(msg).encode('utf-8'), LUA_OUTCOMING_ADDR)

                # print all other messages
                print("\n<<", json.dumps(msg, indent=2), "\n")
            except Exception as e:
                print('[Listener error] ', e)

    threading.Thread(target=listen, daemon=True).start()

def main():
    # set up UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)

    # get player ID
    player_id = start_lua_bridge(sock)
    start_server_listener(sock, player_id)
    print(f"[Client] Running for player_id: {player_id}")
    while not shutdown.is_set():
        time.sleep(0)
    
    sock.close()
            

    # # start listener thread
    # threading.Thread(target=listen, args=(sock, player_id), daemon=True).start()

    # # show available commands
    # print("\n=== Commands ===")
    # for i, c in enumerate(COMMANDS, 1):
    #     print(f"  {i}. {c['name']}")
    # print("================\n")

    # # command loop
    # while True:
    #     choice = input("Choose command number (or 'q' to quit): ").strip()
    #     if choice.lower() in ('q', 'quit', 'exit'):
    #         break
    #     if not choice.isdigit() or not (1 <= int(choice) <= len(COMMANDS)):
    #         print("Invalid choice, try again.")
    #         continue

    #     cmd = COMMANDS[int(choice) - 1]
    #     msg = build_message(cmd, player_id)
    #     if msg:
    #         sock.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)

    # sock.close()

if __name__ == "__main__":
    main()
