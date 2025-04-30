
# Game Server README

## Overview

This UDP-based game server maintains a shared **game state** and broadcasts updates to all connected clients. It supports the following features:

- **Waiting room & ready-up**: Players join a lobby, set ready, and start the game when everyone is ready.  
- **Movement & shooting**: Tanks move on a bounded map and fire bullets.  
- **Health & damage**: Each player has `hp`; bullets deal damage on hit.  
- **Heartbeat**: Server pings clients; clients reply with `pong` to stay “alive.”  
- **Game loop**: Runs at 60 Hz to move bullets, detect collisions, expire bullets, and broadcast state.

---

> **Note:**  
> - All messages are plain UDP-JSON, no additional framing or compression.  
> - Clients must reply **`pong`** within 30 s of each `ping` to stay connected.  
> - **Health (`hp`)** starts at 100; each bullet inflicts 25 hp damage.  
> - Players with `hp ≤ 0` are “destroyed” but remain in `game_state` until they `leave` or disconnect.

---

## API Specification

### 1. Client → Server Messages

| Action                    | Description                                               | Required Fields                      |
|---------------------------|-----------------------------------------------------------|--------------------------------------|
| `list_rooms`              | Request list of all available rooms.                      | `player_id`                          |
| `create_room`             | Create a new room with a unique human-readable name.      | `player_id`, `room_name`             |
| `join_room`               | Join any room (fallback, picks first if no ID/name).      | `player_id`                          |
| `join_room_by_name`       | Join an existing room by its name.                        | `player_id`, `room_name`             |
| `join_room_by_id`         | Join an existing room by its ID.                          | `player_id`, `room_id`               |
| `delete_room_by_name`     | Delete a room by its name (if > 1 room remains).          | `player_id`, `room_name`             |
| `delete_room_by_id`       | Delete a room by its ID (if > 1 room remains).            | `player_id`, `room_id`               |
| `set_ready`               | Mark yourself ready and spawn at initial position.        | `player_id`                          |
| `start_game`              | Start the game when all in waiting room are ready.        | `player_id`                          |
| `move`                    | Move to a new position and facing direction.              | `player_id`, `position: {x, y}`, `direction` |
| `shoot`                   | Fire a bullet in your tank’s current direction.           | `player_id`                          |
| `leave`                   | Leave the game (removes you from room).                   | `player_id`                          |
| `chat`                    | Send a chat message (logged by server).                   | `player_id`, `message`               |
| `revive` (debug)          | Reset your `hp` to 100 (for testing).                     | `player_id`                          |
| `pong`                    | Reply to server `ping` to stay connected.                 | `player_id`                          |

### 2. Server → Client Messages

| Action                    | Description                                               | Fields                              |
|---------------------------|-----------------------------------------------------------|-------------------------------------|
| `rooms_list`              | Delivers current list of rooms.                           | `rooms: [{room_id, room_name}]`, `timestamp` |
| `create_room_response`    | Acknowledges room creation (success/failure).             | `success`, `room_id`, `room_name`   |
| `join_room_response`      | Acknowledges join request (by name/ID).                   | `success`, `room_id`, `room_name`   |
| `delete_room_response`    | Acknowledges room deletion (success/failure).             | `success`, `room_id`, `room_name`   |
| `update_state`            | Full dump of `game_state` after any event.                | `game_state`, `timestamp`           |
| `ping`                    | Heartbeat request — clients must reply with `pong`.       | none                                |

---

Below is the **Message Templates** section rewritten in the same “Example: …” style you showed, with fenced JSON blocks. You can drop this into your README under **API Specification**.

---

## 3. Message Templates

### 3.1 Client → Server Examples

#### Example: List Rooms

```json
{
  "action": "list_rooms",
  "player_id": "<player_id>"
}
```

#### Example: Create Room

```json
{
  "action": "create_room",
  "player_id": "<player_id>",
  "room_name": "<room_name>"
}
```

#### Example: Join Room (fallback)

```json
{
  "action": "join_room",
  "player_id": "<player_id>"
}
```

#### Example: Join by Name

```json
{
  "action": "join_room_by_name",
  "player_id": "<player_id>",
  "room_name": "<room_name>"
}
```

#### Example: Join by ID

```json
{
  "action": "join_room_by_id",
  "player_id": "<player_id>",
  "room_id": "<room_id>"
}
```

#### Example: Delete by Name

```json
{
  "action": "delete_room_by_name",
  "player_id": "<player_id>",
  "room_name": "<room_name>"
}
```

#### Example: Delete by ID

```json
{
  "action": "delete_room_by_id",
  "player_id": "<player_id>",
  "room_id": "<room_id>"
}
```

#### Example: Set Ready

```json
{
  "action": "set_ready",
  "player_id": "<player_id>"
}
```

#### Example: Start Game

```json
{
  "action": "start_game",
  "player_id": "<player_id>"
}
```

#### Example: Move

```json
{
  "action": "move",
  "player_id": "<player_id>",
  "position": { "x": <number>, "y": <number> },
  "direction": "<up|down|left|right>"
}
```

#### Example: Shoot

```json
{
  "action": "shoot",
  "player_id": "<player_id>"
}
```

#### Example: Leave Game

```json
{
  "action": "leave",
  "player_id": "<player_id>"
}
```

#### Example: Chat

```json
{
  "action": "chat",
  "player_id": "<player_id>",
  "message": "<text>"
}
```

#### Example: Revive (debug)

```json
{
  "action": "revive",
  "player_id": "<player_id>"
}
```

#### Example: Pong (Heartbeat)

```json
{
  "action": "pong",
  "player_id": "<player_id>"
}
```

---

### 3.2 Server → Client Examples

#### Example: Rooms List

```json
{
  "action": "rooms_list",
  "rooms": [
    { "room_id": "<room_id>", "room_name": "<room_name>" }
  ],
  "timestamp": <unix_epoch_seconds>
}
```

#### Example: Create Room Response

```json
{
  "action": "create_room_response",
  "success": <true|false>,
  "room_id": "<room_id>",
  "room_name": "<room_name>"
}
```

#### Example: Join Room Response

```json
{
  "action": "join_room_response",
  "success": <true|false>,
  "room_id": "<room_id>",
  "room_name": "<room_name>"
}
```

#### Example: Delete Room Response

```json
{
  "action": "delete_room_response",
  "success": <true|false>,
  "room_id": "<room_id>",
  "room_name": "<room_name>"
}
```

#### Example: Update State

```json
{
  "action": "update_state",
  "timestamp": <unix_epoch_seconds>,
  "game_state": {
    "name": "<room_name>",
    "waiting_room": [ "<player_id>", /* … */ ],
    "players": {
      "<player_id>": {
        "ready": <true|false>,
        "position": { "x": <number>, "y": <number> } | null,
        "direction": "<up|down|left|right>" | null,
        "hp": <number>,
        "address": [ "<ip>", <port> ],
        "last_pong": <unix_epoch_seconds>
      }
      /* … */
    },
    "bullets": [
      {
        "owner": "<player_id>",
        "x": <number>,
        "y": <number>,
        "direction": "<up|down|left|right>",
        "spawn_time": <unix_epoch_seconds>
      }
      /* … */
    ]
  }
}
```

#### Example: Ping

```json
{
  "action": "ping"
}
```
---

## New Server Logic

1. **Automatic removal from previous rooms**  
    When a player successfully joins a new room (`join_room`, `join_room_by_name`, or `join_room_by_id`), the server first removes them from any prior room’s `players` list and waiting queue, then broadcasts updated `update_state` to those old rooms. This ensures each player occupies exactly one room at a time.
    
2. **Broadcast updated rooms list**  
    After every successful `create_room`, `delete_room_by_name`, or `delete_room_by_id`, the server sends an updated `rooms_list` to **all** connected clients (both in lobbies and in-game), keeping everyone synchronized with available rooms.
    

---

> **Reminder:**
> 
> - Reply to each `ping` with `pong` to stay connected.
>     
> - Use the JSON templates above to craft valid messages for testing.
>     
> - For custom testing, you can always send a raw JSON message via your client.
>