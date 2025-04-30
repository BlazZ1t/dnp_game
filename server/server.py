import asyncio        # for asynchronous I/O, event loop, and tasks
import json           # for JSON serialization/deserialization
import time           # for timestamps and sleeping
import math           # for distance calculation (hit detection)
import random         # for assignment of player positions
import uuid           # for generating unique room IDs

# ----------------------------------------
# World parameters (game map and bullets)
# ----------------------------------------
MAP_WIDTH       = 800     # map width in pixels (x from 0 to MAP_WIDTH)
MAP_HEIGHT      = 600     # map height in pixels (y from 0 to MAP_HEIGHT)
BULLET_LIFETIME = 3.0     # how long a bullet lives (seconds) before disappearing
BULLET_SPEED    = 300     # bullet speed (pixels per second)
PLAYER_RADIUS   = 20      # approximate radius of a tank (for hit detection)
BULLET_DAMAGE   = 25      # how much HP a bullet removes on hit

# ------------------------
# Server timing parameters
# ------------------------
TICK_RATE     = 60        # how many game updates per second
PING_INTERVAL = 10        # how often server sends ping messages (seconds)
PONG_TIMEOUT  = 30        # how long to wait for a pong before disconnecting (seconds)


rooms = {}              # room_id -> room_info dict (stores information about each room)
name_to_id = {}         # room_name -> room_id (maps room names to their unique room ID)

temp_players = {}         # dict: player_id -> player info dict. Is here to handle pongs to the clients who are not yet in a room but need to be pinged

def create_room(room_name=None):
     return {
    'name': room_name,     # the human-readable name of the room (could be set by the player when creating the room)
    'waiting_room': [],    # list of player_ids who are waiting in the room's lobby
    'players': {},         # player_id -> player info (stores data like position, health, etc.)
    'bullets': []          # list of active bullets (bullets in motion during gameplay)
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
    print(json.dumps(temp_players, indent=2, ensure_ascii=False), "\n")


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

# --------------------------------------------
# Send list of the available rooms to the user
# --------------------------------------------
async def send_room_list(transport, addr):
     # Construct a message with a list of available rooms, including both room ID and name for clarity
    message = {
        "action": "rooms_list",
        "rooms": [
            {"room_id": rid, "room_name": info['name']}  # each room contains its unique ID and name
            for rid, info in rooms.items()
        ]
    }
    data = json.dumps(message).encode('utf-8')
    transport.sendto(data, addr)


# -----------------------------------------------------------------------------
# broadcast the current rooms list to every connected client
# -----------------------------------------------------------------------------
async def broadcast_room_list_to_all(transport):
    """
    Send an updated 'rooms_list' message to:
      1) every client in the lobby (temp_players), and
      2) every client already inside any room (rooms[*]['players']).
    This ensures everyone sees room creations or deletions immediately.
    """
    # 1) Clients waiting in lobby
    for pid, info in temp_players.items():
        await send_room_list(transport, info['address'])

    # 2) Clients already in rooms
    for rid, state in rooms.items():
        for p_id, p_info in state['players'].items():
            await send_room_list(transport, p_info['address'])





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
    room_id   = msg.get('room_id')      # the ID of the room the client wants to join or is in
    room_name = msg.get('room_name')    # the room name (used for create_room and join_room_by_name actions)

    # require both fields
    if not action or not player_id:
        return

    if not room_id and action not in (
        'list_rooms', 'create_room',
        'join_room', 'join_room_by_name', 'join_room_by_id',
        'delete_room_by_name', 'delete_room_by_id'):
        # find a room where player placed
        for rid, state in rooms.items():
            if player_id in state['players']:
                room_id = rid
                break

    #
    # ========== New Endpoint: list_rooms ==========
    # This endpoint returns a list of all available rooms with their IDs and names.
    #
    if action == 'list_rooms':
        await send_room_list(transport, addr)  # Respond with the list of rooms
        return

    #
    # ========== New Endpoint: create_room ==========
    # This endpoint allows players to create a new room. The player provides a room_name, and a unique room_id is generated.
    #
    if action == 'create_room':
        if not room_name:
            # If no room name is provided, respond with an error
            err = {'action':'create_room_response',
                   'success': False,
                   'error': 'room_name is required'}
            transport.sendto(json.dumps(err).encode(), addr)
            return
        if room_name in name_to_id:
            # If the room name is already taken, respond with an error
            err = {'action':'create_room_response',
                   'success': False,
                   'error': 'room_name already exists'}
            transport.sendto(json.dumps(err).encode(), addr)
            return
        # Generate a unique room ID
        while True:
            new_id = uuid.uuid4().hex  # Using UUID for generating unique room IDs
            if new_id not in rooms:
                break
        # Create the room with the provided name and the unique ID
        rooms[new_id] = create_room(room_name)
        name_to_id[room_name] = new_id  # Map the room name to the room ID
        # Send success response with the room ID and name
        resp = {'action':'create_room_response',
                'success': True,
                'room_id': new_id,
                'room_name': room_name}
        transport.sendto(json.dumps(resp).encode(), addr)
        await broadcast_room_list_to_all(transport)
        return

    #
    # ========== New Endpoint: join_room_by_name ==========
    # This endpoint allows players to join a room by its name. The server maps the name to a room ID.
    #
    if action == 'join_room_by_name':
        if not room_name or room_name not in name_to_id:
            # If the room name is not found, respond with an error
            err = {'action':'join_room_response',
                   'success': False,
                   'error': 'room_name not found'}
            transport.sendto(json.dumps(err).encode(), addr)
            return
        room_id = name_to_id[room_name]  # Retrieve the room ID using the room name
        action = 'join_room'  # Proceed with the join_room action

    #
    # ========== New Endpoint: join_room_by_id ==========
    # This endpoint allows players to join a room using its unique ID.
    #
    if action == 'join_room_by_id':
        if not room_id or room_id not in rooms:
            # If the room ID is not found, respond with an error
            err = {'action':'join_room_response',
                   'success': False,
                   'error': 'room_id not found'}
            transport.sendto(json.dumps(err).encode(), addr)
            return
        action = 'join_room'  # Proceed with the join_room action

    #
    # ========== New Endpoint: delete_room_by_id ==========
    # Allows deleting a room by its unique ID, unless it's the last room.
    #
    if action == 'delete_room_by_id':
        # If there's only one room left, we refuse to delete it
        if len(rooms) <= 1:
            err = {
                'action': 'delete_room_response',
                'success': False,
                'error': 'cannot delete the last remaining room'
            }
            transport.sendto(json.dumps(err).encode(), addr)
            return
        # Make sure the room_id exists
        if not room_id or room_id not in rooms:
            err = {
                'action': 'delete_room_response',
                'success': False,
                'error': 'room_id not found'
            }
            transport.sendto(json.dumps(err).encode(), addr)
            return
        # Remove the room from both mappings
        removed_name = rooms[room_id]['name']
        del rooms[room_id]
        # Clean up the name->id map as well
        if removed_name in name_to_id:
            del name_to_id[removed_name]
        # Send success response
        resp = {
            'action': 'delete_room_response',
            'success': True,
            'room_id': room_id,
            'room_name': removed_name
        }
        transport.sendto(json.dumps(resp).encode(), addr)
        await broadcast_room_list_to_all(transport)
        return

    #
    # ========== New Endpoint: delete_room_by_name ==========
    # Allows deleting a room by its human-readable name, unless it's the last room.
    #
    if action == 'delete_room_by_name':
        # If there's only one room left, we refuse to delete it
        if len(rooms) <= 1:
            err = {
                'action': 'delete_room_response',
                'success': False,
                'error': 'cannot delete the last remaining room'
            }
            transport.sendto(json.dumps(err).encode(), addr)
            return
        # Make sure the room_name exists
        if not room_name or room_name not in name_to_id:
            err = {
                'action': 'delete_room_response',
                'success': False,
                'error': 'room_name not found'
            }
            transport.sendto(json.dumps(err).encode(), addr)
            return
        # Locate the room_id, then remove from both maps
        rid = name_to_id[room_name]
        del rooms[rid]
        del name_to_id[room_name]
        # Send success response
        resp = {
            'action': 'delete_room_response',
            'success': True,
            'room_id': rid,
            'room_name': room_name
        }
        transport.sendto(json.dumps(resp).encode(), addr)
        return



    #
    # ========== Auto-join (Fallback) ==========
    # If the client sends a join_room request without a room ID, automatically place them in the first available room
    # or create a new room if there are no existing rooms.
    #
    if action == 'join_room' and not room_id:
        if rooms:
            # Automatically join the first room in the list (first created room)
            room_id = next(iter(rooms))
        else:
            # If there are no rooms, create a new room with a unique ID
            while True:
                default_id = uuid.uuid4().hex  # Generate a unique room ID
                if default_id not in rooms:
                    break
            default_name = default_id  # Use the room ID as the default room name
            rooms[default_id] = create_room(default_name)  # Create the new room
            name_to_id[default_name] = default_id  # Map the default name to the room ID
            room_id = default_id  # Assign the generated room ID

    # If room_id is still not set, the client is not in any room yet. Send the list of rooms
    if not room_id:
        # The player is not in any room yet; handle ping/pong and show the room list
        if action == 'pong':
            if player_id in temp_players:
                temp_players[player_id]['last_pong'] = time.time()  # Update ping time
        else:
            # The player is not in a room yet, temporarily store them and send the list of available rooms
            if player_id not in temp_players:
                temp_players[player_id] = {
                    'ready': False,
                    'position': None, 'direction': None,
                    'hp': 100, 'address': addr,
                    'last_pong': time.time()
                }
        await send_room_list(transport, addr)
        return
    else:
        # If the player was previously in temp_players, remove them from temp storage since they have joined a room
        temp_players.pop(player_id, None)
    
    # ----------------------------
    # Create room if there is none
    # ----------------------------
    if room_id not in rooms:
        # Legacy support: if the room ID does not exist, create a room with the ID as the room name
        rooms[room_id] = create_room(room_name=room_id)  # Use the room ID as the room name
        name_to_id[room_id] = room_id  # Map the room name to its unique ID

    game_state = rooms[room_id]

    # -------------------
    # Handle 'pong' reply
    # -------------------
    if action == 'pong':
        # update last-seen timestamp if player exists
        if player_id in game_state['players']:
            game_state['players'][player_id]['last_pong'] = time.time()
        return  # pong is not broadcast

    # -------------------------------------
    # Handle new player joining the waiting room
    # -------------------------------------
    if action == 'join_room':
        
        #Remove this player from any previous room before joining
        for old_rid, gs in rooms.items():
            # If they were in the players dict, drop them
            if player_id in gs['players']:
                del gs['players'][player_id]
            # If they were still in the waiting_room list, remove them
            if player_id in gs['waiting_room']:
                gs['waiting_room'].remove(player_id)
            # Notify the remaining players in that old room
            if old_rid != room_id:
                await broadcast_state(transport, old_rid)
        # if completely new player
        if player_id not in game_state['players']:
            # initialize player info
            game_state['players'][player_id] = {
                'ready': False,         # has not signaled ready yet
                'position': None,       # will be set on ready
                'direction': None,      # will be set on ready
                'hp': 100,              # starting health points
                'address': addr,        # UDP address tuple
                'last_pong': time.time()# last pong timestamp
            }
            game_state['waiting_room'].append(player_id)
            print_state(f"Player '{player_id}' joined waiting room (hp=100)")
        else:
            # returning player: just update address and pong time
            p = game_state['players'][player_id]
            p['address']   = addr
            p['last_pong'] = time.time()

        # --------------------------------------------------------------------------------
        # Send explicit join_room_response to the requesting client
        # --------------------------------------------------------------------------------
        # We send this before broadcasting the full state so the client immediately
        # knows which room it has joined and whether the join succeeded.
        resp = {
            'action': 'join_room_response',
            'success': True,
            'room_id':   room_id,             # Unique identifier for this room
            'room_name': game_state['name']   # Human-readable name of this room
        }
        transport.sendto(json.dumps(resp).encode('utf-8'), addr)

        # --------------------------------------------------------------------------------
        # Broadcast updated state to all players in the room
        # --------------------------------------------------------------------------------
        # After confirming to the new player, send the complete game state
        # (player lists, ready flags, etc.) to everyone so all clients stay in sync.
        await broadcast_state(transport, room_id)
        return  # Exit early to prevent further action handling for this packet  :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}

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
            'position': {'x': 100, 'y': 100},
            'direction': 'up'
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
        print(f"[chat] {player_id}@{room_id}: {text}")

    # ----------------------------------
    # After handling any of the above,
    # broadcast updated game state
    # ----------------------------------
    await broadcast_state(transport, room_id)


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
            game_state['bullets'] = new_bullets

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
        print(temp_players)
        for pid, info in list(temp_players.items()):
            # ping players who are not yet in a room
            print(f"Ping {pid} with no room at {info['address']}")
            transport.sendto(ping_msg, info['address'])
        # remove inactive players
        cutoff = now - PONG_TIMEOUT
        for pid, info in list(temp_players.items()):
            if info['last_pong'] < cutoff:
                del temp_players[pid]

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
