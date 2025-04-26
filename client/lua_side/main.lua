local socket = require "socket"
local json = require "json" -- You'll need to add a JSON library

math.randomseed(os.time())

local game_state = {
    waiting_room = {},
    players = {},
    bullets = {}
}

local resources = {
    button_normal = love.graphics.newImage("assets/button_rectangle_depth_flat.png"),
    button_hover = love.graphics.newImage("assets/button_rectangle_depth_flat.png"),
    button_pressed = love.graphics.newImage("assets/button_rectangle_flat.png"),
    -- background = love.graphics.newImage("lobby_bg.jpg"),
    font_heading = love.graphics.newFont("assets/Kenney Future.ttf", 40),
    font_body = love.graphics.newFont("assets/Kenney Future.ttf", 20),
    click_sound = love.audio.newSource("assets/click.ogg", "static"),

    tank_up = love.graphics.newImage("assets/tank_up.png"),
    tank_down = love.graphics.newImage("assets/tank_down.png"),
    tank_left = love.graphics.newImage("assets/tank_left.png"),
    tank_right = love.graphics.newImage("assets/tank_right.png"),
}

local network = {
    udp = socket.udp(),
    server_ip = "127.0.0.1",
    server_port = 9999,
    player_id = "player_" .. tostring(math.random(1000, 9999)),
    player_direction = "",
    player_last_direction = "",
    player_position = { x = 0, y = 0 },
    player_speed = { vx = 0, vy = 0 },
    last_ping = 0,
    last_move = 0,
    last_sent_position = { x = 0, y = 0 },
}

local lobby = {

    show_lobby = true,
    ready = false,
    buttons = {
        ready = {
            x = 300,
            y = 400,
            w = 200,
            h = 50,
            state = "normal", -- can be normal/hover/pressed
            text = "Ready"
        },
        start = {
            x = 300,
            y = 500,
            w = 200,
            h = 50,
            state = "normal",
            text = "Start"
        }
    }
}

local function allPlayersReady()
    count = 0
    for _, player in pairs(game_state.players) do
        if not player.ready then
            return false
        end
        count = count + 1
    end
    -- Ony true if more than 2 players
    return count >= 2
end

function connectToServer()
    network.udp:settimeout(0)
    network.udp:setpeername(network.server_ip, network.server_port)
    sendNetworkMessage({
        action = "join_room",
        player_id = network.player_id
    })
end

function love.threaderror(thread, error)
    print("Network thread error:", error)
end

function sendNetworkMessage(msg)
    local data = json.encode(msg)
    network.udp:send(data)
end

function love.load()
    love.window.setTitle("Tank Battle - Lobby")
    love.window.setMode(800, 600)
    connectToServer()
end

function love.update(dt)
    -- Love is buggy!!!! This dt thing is not reliable

    if network.player_speed.vx ~= 0 or network.player_speed.vy ~= 0 then
        local new_position = network.player_position
        new_position.x = network.player_position.x + (network.player_speed.vx * dt)
        new_position.y = network.player_position.y + (network.player_speed.vy * dt)
        network.player_position = new_position
    end


    -- this is spam, but lets think it is OK :)
    sendNetworkMessage({
        action = "move",
        player_id = network.player_id,
        position = network.player_position,
        direction = network.player_direction
    })

    -- Network receiving
    while true do
        local data, err = network.udp:receive()
        if not data then
            if err == 'timeout' then
                break -- No more data to read
            else
                print("Network error:", err)
                break
            end
        end
        local success, msg = pcall(json.decode, data)
        if success then
            handleNetworkMessage(msg)
        else
            print("JSON decode error:", msg)
        end
    end
end

function handleNetworkMessage(msg)
    if msg.action == "update_state" then
        -- Print "Update state"
        game_state = msg.game_state
        -- Check if we are in players, but the waiting_room is empty - this means game started
        if game_state.players[network.player_id] and next(game_state.waiting_room) == nil then
            lobby.show_lobby = false
            network.player_position = game_state.players[network.player_id].position
        end
        game_state.players[network.player_id].position = network.player_position
    elseif msg.action == "ping" then
        sendNetworkMessage({
            action = "pong",
            player_id = network.player_id
        })
    elseif msg.action == "game_start" then
        lobby.show_lobby = false
        network.player_position = game_state.players[network.player_id].position
    end
end

function love.draw()
    if lobby.show_lobby then
        drawLobby()
    else
        drawGame()
    end
end

-- Game related

function drawTank(x, y, hp, id, direction)
    -- Draw tank
    love.graphics.setColor(1, 0, 0)

    local img = resources.tank_up
    if direction == "down" then
        img = resources.tank_down
    elseif direction == "left" then
        img = resources.tank_left
    elseif direction == "right" then
        img = resources.tank_right
    end
    love.graphics.draw(img, x - 20, y - 20)
end

function drawPlayer()
    -- Draw player tank
    love.graphics.setColor(0, 0, 1)

    local img = resources.tank_up
    if network.player_direction == "" then
        if network.player_last_direction == "down" then
            img = resources.tank_down
        elseif network.player_last_direction == "left" then
            img = resources.tank_left
        elseif network.player_last_direction == "right" then
            img = resources.tank_right
        end
    else
        if network.player_direction == "down" then
            img = resources.tank_down
        elseif network.player_direction == "left" then
            img = resources.tank_left
        elseif network.player_direction == "right" then
            img = resources.tank_right
        end
    end
    love.graphics.draw(img, network.player_position.x - 20, network.player_position.y - 20)
end

function drawGame()
    for player_id, player in pairs(game_state.players) do
        if player_id == network.player_id then
            drawPlayer()
        else
            drawTank(player.position.x, player.position.y, player.hp, player_id, player.direction)
        end
    end
end

function love.keypressed(key)
    if key == "w" then
        network.player_direction = "up"
        network.player_speed.vy = -200
    elseif key == "a" then
        network.player_direction = "left"
        network.player_speed.vx = -200
    elseif key == "s" then
        network.player_direction = "down"
        network.player_speed.vy = 200
    elseif key == "d" then
        network.player_direction = "right"
        network.player_speed.vx = 200
    end
end

function love.keyreleased(key)
    if key == "w" then
        network.player_last_direction = "up"
        network.player_direction = ""
        network.player_speed.vy = 0
    elseif key == "a" then
        network.player_last_direction = "left"
        network.player_direction = ""
        network.player_speed.vx = 0
    elseif key == "s" then
        network.player_last_direction = "down"
        network.player_direction = ""
        network.player_speed.vy = 0
    elseif key == "d" then
        network.player_last_direction = "right"
        network.player_direction = ""
        network.player_speed.vx = 0
    end
end

-- Lobby related

function drawButton(button)
    local img = resources.button_normal
    if button.state == "hover" then
        img = resources.button_hover
    elseif button.state == "pressed" then
        img = resources.button_pressed
    end

    -- Scale image to button dimensions
    local scale_x = button.w / img:getWidth()
    local scale_y = button.h / img:getHeight()

    love.graphics.setColor(1, 1, 1)
    love.graphics.draw(img, button.x, button.y, 0, scale_x, scale_y)

    -- Draw button text
    love.graphics.setFont(resources.font_body)
    love.graphics.setColor(1, 1, 1)
    love.graphics.printf(button.text, button.x, button.y + button.h / 3, button.w, "center")
end

function drawLobby()
    love.graphics.setColor(1, 1, 1)
    love.graphics.print("Lobby - Player ID: " .. network.player_id, 20, 20)

    -- Draw players list
    local y = 60
    love.graphics.print("Players in room:", 20, y)
    y = y + 30

    for player_id, player in pairs(game_state.players) do
        local status = player.ready and "Ready" or "Not Ready"
        if status == "Ready" then
            love.graphics.setColor(0, 1, 0)
        else
            love.graphics.setColor(1, 0, 0)
        end

        love.graphics.print(string.format("%s - %s", player_id, status), 40, y)
        y = y + 25
    end

    -- Draw buttons
    if not lobby.ready then
        drawButton(lobby.buttons.ready)
    end
    if allPlayersReady() then
        drawButton(lobby.buttons.start)
    end
end

function love.mousemoved(x, y)
    if lobby.show_lobby then
        for _, btn in pairs(lobby.buttons) do
            if isPointInRect(x, y, btn) then
                btn.state = "hover"
            else
                btn.state = "normal"
            end
        end
    end
end

function love.mousepressed(x, y, button)
    if lobby.show_lobby and button == 1 then
        -- Ready button
        if isPointInRect(x, y, lobby.buttons.ready) then
            lobby.buttons.ready.state = "pressed"
            resources.click_sound:play()
            sendNetworkMessage({
                action = "set_ready",
                player_id = network.player_id
            })
            lobby.ready = not lobby.ready

            -- Start button
        elseif allPlayersReady() and isPointInRect(x, y, lobby.buttons.start) then
            lobby.buttons.start.state = "pressed"
            resources.click_sound:play()
            sendNetworkMessage({
                action = "start_game",
                player_id = network.player_id
            })
        end
    end
end

function love.mousereleased(x, y, button)
    if lobby.show_lobby and button == 1 then
        -- Ready button
        if isPointInRect(x, y, lobby.buttons.ready) then
            lobby.buttons.ready.state = "hover"
            -- Start button
        elseif allPlayersReady() and isPointInRect(x, y, lobby.buttons.start) then
            lobby.buttons.start.state = "hover"
        end
    end
end

function isPointInRect(x, y, rect)
    return x >= rect.x and x <= rect.x + rect.w and
        y >= rect.y and y <= rect.y + rect.h
end
