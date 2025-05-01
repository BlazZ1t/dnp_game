# Game Server README

## Overview

This UDP-based game server maintains a shared **game state** and broadcasts updates to all connected clients. It supports the following features:

- **Waiting room & ready‑up**: Players join a lobby, set ready, and start the game when everyone is ready.
    
- **Movement & shooting**: Tanks move on a bounded map and fire bullets.
    
- **Health & damage**: Each player has `hp`; bullets deal damage on hit.
    
- **Heartbeat**: Server pings clients; clients reply with `pong` to stay “alive.”
    
- **Game loop**: Runs at 60 Hz to move bullets, detect collisions, expire bullets, and broadcast state.
    
- **Timeout**: Players who miss 30 s of pings are removed automatically.
    

---

## High‑Level Architecture

1. **UDP Listener**  
    The server binds to `0.0.0.0:9999` (or `127.0.0.1:9999` in development). Every incoming packet spawns an `asyncio` task `handle_client(addr, data, transport)`.
    
2. **Message Handling**
    
    - Parse JSON: `{ action: string, player_id: string, … }`.
        
    - **join_room** registers a new player.
        
    - **set_ready**, **move**, **shoot**, **start_game**, **leave**, **chat** update the `game_state` and immediately trigger a broadcast.
        
    - **pong** updates the player's last‑seen timestamp (no broadcast).
        
    - Unrecognized or malformed messages are ignored.
        
3. **Broadcast Loop**  
    On every game event and every bullet tick, the full `game_state` is JSON‑serialized and sent to each `player.address`.
    
4. **Game Tick** (60 Hz)
    
    - Moves each bullet by `speed × Δt`.
        
    - Removes bullets that leave the map or exceed `lifetime`.
        
    - Checks bullet‑vs‑player collisions: if within `PLAYER_RADIUS`, subtract `BULLET_DAMAGE` from `hp`, log “hit” or “kill,” and drop the bullet.
        
5. **Ping Loop**  
    Every `PING_INTERVAL` seconds, sends `{ action: "ping" }` to all players. If any player’s `last_pong` is older than `PONG_TIMEOUT`, they are removed from `game_state`.
    

---

## API Specification

### 1. Client → Server Messages

|Action|Description|Required Fields|
|---|---|---|
|`join_room`|Join the waiting room (or reconnect).|`player_id`|
|`set_ready`|Mark yourself ready and spawn at initial position.|`player_id`|
|`move`|Move to a new position and facing direction.|`player_id`, `position: {x, y}`, `direction`|
|`shoot`|Fire a bullet in the tank’s current direction.|`player_id`|
|`start_game`|Start when all in waiting room are ready (≥ 2 players).|`player_id`|
|`leave`|Leave the game (removes you).|`player_id`|
|`chat`|Send chat text to server log (not broadcast to others).|`player_id`, `message`|
|`pong`|Reply to server “ping” to stay connected.|`player_id`|

#### Example: Join Room

```json
{
  "action": "join_room",
  "player_id": "alice",
  "room_name": "room_1"
}
```

#### Example: Ready Up

```json
{
  "action": "set_ready",
  "player_id": "alice"
}
```

#### Example: Move

```json
{
  "action": "move",
  "player_id": "alice",
  "position": { "x": 150, "y": 200 },
  "direction": "left"
}
```

#### Example: Shoot

```json
{
  "action": "shoot",
  "player_id": "alice"
}
```

#### Example: Pong (Heartbeat)

```json
{
  "action": "pong",
  "player_id": "alice"
}
```

---

### 2. Server → Client Messages

|Action|Description|Fields|
|---|---|---|
|`update_state`|Full dump of current `game_state` (after any event)|`game_state`, `timestamp`|
|`ping`|Heartbeat request — client must reply with `pong`.|none|

#### Example: Ping

```json
{ 
  "action": "ping" 
}
```

#### Example: Update State

```json
{
  "action": "update_state",
  "timestamp": 1625050201.123,
  "game_state": {
    "waiting_room": ["alice","bob"],
    "players": {
      "alice": {
        "ready": true,
        "position": { "x": 150, "y": 200 },
        "direction": "left",
        "hp": 75,
        "address": ["127.0.0.1",9999],
        "last_pong": 1625050198.456
      },
      "bob": {
        "ready": false,
        "position": null,
        "direction": null,
        "hp": 100,
        "address": ["127.0.0.1",9998],
        "last_pong": 1625050190.789
      }
    },
    "bullets": [
      {
        "player_id": "alice",
        "position": { "x": 150, "y": 200 },
        "direction": "left",
        "created": 1625050200.000
      }
    ]
  }
}
```

---

## Detailed Flow & Examples

1. **Player ‘alice’ sends `join_room`.**
    
    ```python
    if action == 'join_room':
        game_state['players'][player_id] = {
            'ready': False, 'position': None, 'direction': None,
            'hp': 100, 'address': addr, 'last_pong': time.time()
        }
        game_state['waiting_room'].append(player_id)
        print_state("Player 'alice' joined waiting room")
        await broadcast_state()
        return
    ```
    
    Clients receive `update_state` showing `'alice'` in `waiting_room`.
    
2. **Alice sends `set_ready`.**
    
    ```python
    if action == 'set_ready':
        p['ready'] = True
        p['position'] = {'x':100,'y':100}
        p['direction'] = 'up'
        print_state("Player 'alice' set ready")
        await broadcast_state()
    ```
    
    Clients see Alice’s `ready: true` and spawn position.
    
3. **Alice sends `move`.**  
    Server clamps position to bounds, updates and broadcasts.
    
4. **Alice sends `shoot`.**
    
    ```python
    bullet = {
      'player_id': 'alice',
      'position': p['position'].copy(),
      'direction': p['direction'],
      'created': time.time()
    }
    game_state['bullets'].append(bullet)
    print_state("Player 'alice' shot a bullet")
    await broadcast_state()
    ```
    
    Clients see new bullet in `game_state.bullets`.
    
5. **Game Tick (60 Hz).**
    
    ```python
    for b in game_state['bullets']:
        # move bullet by speed*dt
        # if out of bounds or expired: drop
        # else check collision:
        if hit:
            info['hp'] -= BULLET_DAMAGE
            print_state("hit" or "kill")
            drop bullet
    await broadcast_state()
    ```
    
6. **Ping Loop (every 10 s).**
    
    ```python
    for pid in game_state['players']:
        transport.sendto({'action':'ping'})
    # then:
    for pid, info in game_state['players'].items():
        if info['last_pong'] < now - PONG_TIMEOUT:
            del game_state['players'][pid]
            print_state("Player '<id>' disconnected")
    ```
    
    Clients auto‑reply with `pong`.
    

---

> **Note:**
> 
> - All messages are plain UDP‑JSON, no additional framing or compression.
>     
> - Clients must reply **`pong`** within 30 s of each `ping` to stay connected.
>     
> - **Health (`hp`)** starts at 100; each bullet inflicts 25 hp damage.
>     
> - Players with `hp <= 0` are “destroyed” but remain in `game_state` until they `leave` or disconnect.
>