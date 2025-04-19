import socket
import json
import threading

# Server address (host, port)
SERVER_ADDR = ('127.0.0.1', 9999)
BUFFER_SIZE = 65536

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

def listen(sock, player_id):
    """
    Background thread: receive messages from server,
    auto-reply to 'ping' with 'pong', ignore printing pings.
    """
    while True:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            msg = json.loads(data.decode('utf-8'))
        except Exception:
            continue

        action = msg.get('action')
        # auto-reply to ping silently
        if action == 'ping':
            pong = {'action': 'pong', 'player_id': player_id}
            sock.sendto(json.dumps(pong).encode('utf-8'), SERVER_ADDR)
            continue

        # print all other messages
        print("\n<<", json.dumps(msg, indent=2), "\n")

def build_message(cmd, player_id):
    """
    Build a JSON message dict based on the selected command.
    For Custom JSON, prompts raw JSON input.
    """
    if cmd["action"] is None:
        raw = input("Enter full JSON: ").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("Invalid JSON.")
            return None

    msg = {"action": cmd["action"], "player_id": player_id}

    # gather additional params if needed
    if cmd["params"]:
        if cmd["action"] == "move":
            # ask for x, y, direction
            x = input("  x = ").strip()
            y = input("  y = ").strip()
            dir_ = input("  direction (up/down/left/right) = ").strip()
            # convert to numbers if possible
            msg["position"] = {
                "x": int(x) if x.isdigit() else float(x),
                "y": int(y) if y.isdigit() else float(y)
            }
            msg["direction"] = dir_
        elif cmd["action"] == "chat":
            text = input("  message = ").strip()
            msg["message"] = text

    return msg

def main():
    # set up UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)

    # get player ID
    player_id = input("Enter your player_id: ").strip()

    # start listener thread
    threading.Thread(target=listen, args=(sock, player_id), daemon=True).start()

    # show available commands
    print("\n=== Commands ===")
    for i, c in enumerate(COMMANDS, 1):
        print(f"  {i}. {c['name']}")
    print("================\n")

    # command loop
    while True:
        choice = input("Choose command number (or 'q' to quit): ").strip()
        if choice.lower() in ('q', 'quit', 'exit'):
            break
        if not choice.isdigit() or not (1 <= int(choice) <= len(COMMANDS)):
            print("Invalid choice, try again.")
            continue

        cmd = COMMANDS[int(choice) - 1]
        msg = build_message(cmd, player_id)
        if msg:
            sock.sendto(json.dumps(msg).encode('utf-8'), SERVER_ADDR)

    sock.close()

if __name__ == "__main__":
    main()
