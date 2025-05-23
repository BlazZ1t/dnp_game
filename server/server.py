import asyncio        # for asynchronous I/O, event loop, and tasks
import json           # for JSON serialization/deserialization
import time           # for timestamps and sleeping
import math           # for distance calculation (hit detection)
import random         # for assignment of player positions

# ----------------------------------------
# World parameters (game map and bullets)
# ----------------------------------------
MAP_WIDTH       = 800     # map width in pixels (x from 0 to MAP_WIDTH)
MAP_HEIGHT      = 600     # map height in pixels (y from 0 to MAP_HEIGHT)
BULLET_LIFETIME = 3.0     # how long a bullet lives (seconds) before disappearing
BULLET_SPEED    = 700     # bullet speed (pixels per second)
PLAYER_RADIUS   = 20      # approximate radius of a tank (for hit detection)
BULLET_DAMAGE   = 25      # how much HP a bullet removes on hit

# ------------------------
# Server timing parameters
# ------------------------
TICK_RATE     = 60        # how many game updates per second
PING_INTERVAL = 10        # how often server sends ping messages (seconds)
PONG_TIMEOUT  = 30        # how long to wait for a pong before disconnecting (seconds)


# ----------------------------------------
# Pre-created rooms (no dynamic create/delete)
# ----------------------------------------
def create_room(name):
    return {
        'name': name,
        'waiting_room': [],
        'players': {},
        'bullets': [],
        'game_started': False
    }

rooms = {
    'room_1': create_room('room_1'),
    'room_2': create_room('room_2'),
    'room_3': create_room('room_3'),
}

# ---------------------------------------
# Utility: print full game state on event
# ---------------------------------------
def print_state(event: str):
    """
    Print the given event description along with the entire game_state.
    """
    timestamp = time.strftime('%H:%M:%S', time.localtime())  # human-readable time
    print(f"\n[{timestamp}] {event}")                         # header line
    # pretty-print the game_state JSON for debugging
    print(json.dumps(rooms, indent=2, ensure_ascii=False), "\n")


# -----------------------------------------------------
# Broadcast the full game state to all connected players
# -----------------------------------------------------
async def broadcast_state(transport, room_id):
    """
    Send an 'update_state' message containing game_state to every player.
    """
    message = {
        'action': 'update_state',
        'game_state': rooms[room_id],
        'timestamp': time.time(),
    }
    data = json.dumps(message).encode('utf-8')  # encode to bytes
    # send the update to each player's stored address
    for pid, info in list(rooms[room_id]['players'].items()):
        transport.sendto(data, info['address'])


# ---------------------------------------------------
# Handle an incoming UDP packet from a client (player)
# ---------------------------------------------------
async def handle_client(addr, data, transport):
    """
    Parse a JSON message from a client at address 'addr' and update game_state.
    After handling certain actions, broadcast the updated state to all players.
    """
    try:
        msg = json.loads(data.decode('utf-8'))  # decode JSON
    except json.JSONDecodeError:
        return  # ignore non-JSON

    action    = msg.get('action')       # the action that the client wants to perform
    player_id = msg.get('player_id')    # unique identifier for the player
    room_name = msg.get('room_name')    # the room name (used for create_room and join_room_by_name actions)

    # require both fields
    if not action or not player_id:
        return

    # ------------------------------------------------------------
    # Figure out which static room (room_1/2/3) this player is in
    # ------------------------------------------------------------
    current_room = None
    game_state   = None
    for rn, st in rooms.items():
        if player_id in st['players']:
            current_room = rn
            game_state   = st
            break

    # -------------------
    # Handle 'pong' reply
    # -------------------
    if action == 'pong':
        # only update if they’re already in a room
        if game_state:
            game_state['players'][player_id]['last_pong'] = time.time()
        return  # no broadcast for pong    

    # ----------------------------------------------------------------
    # Determine which static room (room_1/2/3) this player is in, if any
    # ----------------------------------------------------------------
    current_room = None
    game_state   = None
    for rn, st in rooms.items():
        if player_id in st['players']:
            current_room = rn
            game_state   = st
            break

    # For any action _other than_ join_room, we need a valid current_room
    if action != 'join_room':
        if not current_room:
            return
        # game_state was already set above

    # -------------------------------------
    # Handle new player joining the waiting room
    # -------------------------------------
    if action == 'join_room':
        # 1) Validate room_name
        room_name = msg.get('room_name')
        if not room_name or room_name not in rooms:
            transport.sendto(json.dumps({
                'action': 'join_room_response',
                'success': False,
                'error': 'invalid or missing room_name'
            }).encode('utf-8'), addr)
            return

        # 2) Remove from any previous room
        for old_name, old_room in rooms.items():
            if player_id in old_room['players']:
                del old_room['players'][player_id]
            if player_id in old_room['waiting_room']:
                old_room['waiting_room'].remove(player_id)
            if old_name != room_name:
                await broadcast_state(transport, old_name)

        # 3) Add (or reconnect) into the new room
        new_room = rooms[room_name]
        if player_id not in new_room['players']:
            new_room['players'][player_id] = {
                'ready': False,
                'position': {'x': random.randint(100, 700), 'y': random.randint(100, 500)},
                'direction': "up",
                'hp': 100,
                'address': addr,
                'last_pong': time.time(),
                'skin': random.randint(1, 4)
            }
            if not new_room['game_started']:
                new_room['waiting_room'].append(player_id)
            else:
                new_room['players'][player_id]['ready'] = True
            print_state(f"Player '{player_id}' joined {room_name}")
        else:
            # reconnecting
            p = new_room['players'][player_id]
            p['address']   = addr
            p['last_pong'] = time.time()

        # 4) Confirm join and broadcast new state
        transport.sendto(json.dumps({
            'action': 'join_room_response',
            'success': True,
            'room_name': room_name
        }).encode('utf-8'), addr)
        await broadcast_state(transport, room_name)
        return
    # ------------------------------------
    # All other actions require a known player
    # ------------------------------------
    if player_id not in game_state['players']:
        return  # ignore unknown players
    p = game_state['players'][player_id]  # shorthand

    # -------------------
    # Player indicates ready
    # -------------------
    if action == 'set_ready':
        # mark ready and give initial spawn position/direction
        p.update({
            'ready': True,
        })
        print_state(f"Player '{player_id}' set ready")

    # -----------------
    # Player movement
    # -----------------
    elif action == 'move':
        pos  = msg.get('position')    # expected dict with 'x' and 'y'
        dir_ = msg.get('direction')   # expected string
        # only move if player is alive and sent valid data
        if pos and dir_ and p['hp'] > 0:
            # clamp within map bounds
            x = max(0, min(MAP_WIDTH, pos.get('x', 0)))
            y = max(0, min(MAP_HEIGHT, pos.get('y', 0)))
            p['position']  = {'x': x, 'y': y}
            p['direction'] = dir_
            print_state(f"Player '{player_id}' moved to {p['position']}")

    # -----------------
    # Player shooting
    # -----------------
    elif action == 'shoot':
        # only shoot if alive and has a valid position
        if p['position'] and p['hp'] > 0:
            # create a new bullet at player's position heading in player's direction
            bullet = {
                'player_id': player_id,              # who fired
                'position': p['position'].copy(),    # starting coords
                'direction': p['direction'],         # heading
                'created': time.time()               # spawn timestamp
            }
            game_state['bullets'].append(bullet)
            print_state(f"Player '{player_id}' shot a bullet (dir={p['direction']})")

    # ----------------
    # Start the game
    # ----------------
    elif action == 'start_game':
        # require at least 2 players and all ready
        game_state['game_started'] = True
        ready_ids = [pid for pid in game_state['waiting_room']
                     if game_state['players'][pid]['ready']]
        if len(game_state['waiting_room']) >= 2 and len(ready_ids) == len(game_state['waiting_room']):
            game_state['waiting_room'].clear()  # clear lobby
            print_state("Game started")

    # ------------------
    # Player leaves game
    # ------------------
    elif action == 'leave':
        # remove from waiting room if present
        if player_id in game_state['waiting_room']:
            game_state['waiting_room'].remove(player_id)
        # delete all player data
        del game_state['players'][player_id]
        if len(game_state['players']) == 0:
            game_state['game_started'] = False
        print_state(f"Player '{player_id}' left the game")
    
    elif action == 'revive':
        p.update({
            'hp': 100,
        })
        print_state(f"Revived '{player_id}'")

    # -------------
    # In-game chat
    # -------------
    elif action == 'chat':
        text = msg.get('message', '')
        # just log chat on server
        print(f"[chat] {player_id}@{current_room}: {text}")

    # ----------------------------------
    # After handling any of the above,
    # broadcast updated game state
    # ----------------------------------
    await broadcast_state(transport, current_room)


# -------------------------------------------------------
# Game update loop: move bullets, detect collisions, etc.
# -------------------------------------------------------
async def game_tick(transport):
    """
    Runs at TICK_RATE Hz. Moves each bullet, checks for
    out-of-bounds or lifetime expiration, and detects hits.
    """
    interval = 1.0 / TICK_RATE  # seconds per tick
    while True:
        now = time.time()            # current time for lifetime checks
        new_bullets = []             # rebuild list of bullets that survive
        for room_id, game_state in rooms.items():

            # process each active bullet
            for b in game_state['bullets']:
                # remove bullet if its lifetime expired
                if now - b['created'] > BULLET_LIFETIME:
                    continue

                # calculate movement for this tick
                distance = BULLET_SPEED * interval
                dx = dy = 0
                if   b['direction'] == 'up':    dy = -distance
                elif b['direction'] == 'down':  dy =  distance
                elif b['direction'] == 'left':  dx = -distance
                else:                            dx =  distance

                # update bullet position
                b['position']['x'] += dx
                b['position']['y'] += dy

                x, y = b['position']['x'], b['position']['y']

                # discard if outside map
                if not (0 <= x <= MAP_WIDTH and 0 <= y <= MAP_HEIGHT):
                    continue

                # check collision with any player (excluding the shooter)
                hit = False
                for pid, info in game_state['players'].items():
                    # skip shooter, dead players, or unspawned
                    if pid == b['player_id'] or info['hp'] <= 0 or not info['position']:
                        continue
                    px, py = info['position']['x'], info['position']['y']
                    # if distance <= PLAYER_RADIUS => hit
                    if math.hypot(px - x, py - y) <= PLAYER_RADIUS:
                        # apply damage
                        info['hp'] -= BULLET_DAMAGE
                        hit = True
                        if info['hp'] <= 0:
                            print_state(f"Player '{pid}' was destroyed by '{b['player_id']}'")
                        else:
                            print_state(f"Player '{pid}' took {BULLET_DAMAGE} damage (hp={info['hp']})")
                        break  # bullet stops on first hit

                # if not hit anyone, keep bullet alive
                if not hit:
                    new_bullets.append(b)

            # replace old bullet list
            game_state['bullets'] = new_bullets.copy()
            new_bullets.clear()

            # broadcast updated bullets (and any hp changes)
            await broadcast_state(transport, room_id)

        # wait until next tick
        await asyncio.sleep(interval)


# ------------------------------------------------------
# Ping loop: detect disconnected clients by heartbeat
# ------------------------------------------------------
async def ping_task(transport):
    """
    Every PING_INTERVAL seconds:
    1) send {'action':'ping'} to each player
    2) remove any player who hasn't responded (last_pong) within PONG_TIMEOUT
    """
    while True:
        now = time.time()
        ping_msg = json.dumps({'action': 'ping'}).encode('utf-8')
        for room_id, game_state in rooms.items():
            # send ping to every player
            for pid, info in list(game_state['players'].items()):
                transport.sendto(ping_msg, info['address'])

            # remove inactive players
            cutoff = now - PONG_TIMEOUT
            for pid, info in list(game_state['players'].items()):
                if info['last_pong'] < cutoff:
                    # if in waiting room, remove from lobby
                    if pid in game_state['waiting_room']:
                        game_state['waiting_room'].remove(pid)
                    # delete player data
                    del game_state['players'][pid]
                    print_state(f"Player '{pid}' disconnected due to timeout")
        await asyncio.sleep(PING_INTERVAL)


# ------------------------------------------
# UDP protocol definition for GameServer
# ------------------------------------------
class GameServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        """
        Called when the UDP socket is created and bound.
        """
        self.transport = transport
        sockname = transport.get_extra_info('sockname')  # (host, port)
        print(f"Server listening on {sockname}")

    def datagram_received(self, data, addr):
        """
        Called whenever a UDP packet arrives.
        Spawns a task to handle it asynchronously.
        """
        asyncio.create_task(handle_client(addr, data, self.transport))


# ------------------------
# Main entry point
# ------------------------
async def main():
    """
    Set up UDP server and schedule background tasks.
    """
    loop = asyncio.get_running_loop()
    # bind to localhost:9999
    transport, _ = await loop.create_datagram_endpoint(
        GameServerProtocol,
        local_addr=('10.247.1.236', 9999)
    )

    # start background loops
    asyncio.create_task(game_tick(transport))
    asyncio.create_task(ping_task(transport))

    # keep server running indefinitely
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
