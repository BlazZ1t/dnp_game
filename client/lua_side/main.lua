local socket = require "socket"
local json = require "json" -- You'll need to add a JSON library
local os = require "os"

math.randomseed(os.time())

local game_state = {
    name = '',
    waiting_room = {},
    players = {},
    bullets = {},
    game_started = false,
}


local resources = {
    button_normal = love.graphics.newImage("assets/button_rectangle_depth_flat.png"),
    button_hover = love.graphics.newImage("assets/button_rectangle_depth_flat.png"),
    button_pressed = love.graphics.newImage("assets/button_rectangle_flat.png"),
    background = love.graphics.newImage("assets/game_background.png"),
    font_title = love.graphics.newFont("assets/Kenney Future.ttf", 60),
    font_heading = love.graphics.newFont("assets/Kenney Future.ttf", 40),
    font_body = love.graphics.newFont("assets/Kenney Future.ttf", 20),
    font_tank = love.graphics.newFont("assets/Kenney Future.ttf", 10),

    click_sound = love.audio.newSource("assets/click.ogg", "static"),
    lobby_music = love.audio.newSource("assets/tetanki_lobby.ogg", "stream"),
    game_music = love.audio.newSource("assets/tetanki_game.ogg", "stream"),

    tank_up_1 = love.graphics.newImage("assets/1_tanks/tank_up.png"),
    tank_down_1 = love.graphics.newImage("assets/1_tanks/tank_down.png"),
    tank_left_1 = love.graphics.newImage("assets/1_tanks/tank_left.png"),
    tank_right_1 = love.graphics.newImage("assets/1_tanks/tank_right.png"),

    tank_up_2 = love.graphics.newImage("assets/2_tanks/tank_up.png"),
    tank_down_2 = love.graphics.newImage("assets/2_tanks/tank_down.png"),
    tank_left_2 = love.graphics.newImage("assets/2_tanks/tank_left.png"),
    tank_right_2 = love.graphics.newImage("assets/2_tanks/tank_right.png"),

    tank_up_3 = love.graphics.newImage("assets/3_tanks/tank_up.png"),
    tank_down_3 = love.graphics.newImage("assets/3_tanks/tank_down.png"),
    tank_left_3 = love.graphics.newImage("assets/3_tanks/tank_left.png"),
    tank_right_3 = love.graphics.newImage("assets/3_tanks/tank_right.png"),

    tank_up_4 = love.graphics.newImage("assets/4_tanks/tank_up.png"),
    tank_down_4 = love.graphics.newImage("assets/4_tanks/tank_down.png"),
    tank_left_4 = love.graphics.newImage("assets/4_tanks/tank_left.png"),
    tank_right_4 = love.graphics.newImage("assets/4_tanks/tank_right.png"),
}

local network = {
    udp = socket.udp(),
    server_ip = "127.0.0.1",
    server_port = 9000,
    player_id = "player_" .. tostring(math.random(1000, 9999)),
    player_skin = 0,
    player_direction = "",
    player_last_direction = "",
    player_position = { x = 0, y = 0 },
    player_speed = { vx = 0, vy = 0 },
    is_alive = true,
    last_ping = 0,
    last_move = 0,
    last_sent_position = { x = 0, y = 0 },
    last_bullet_fired_ts = os.time()
}

local lobby = {

    show_lobby = true,
    choosing_room = true,
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
        },
        back = {
            x = 500,
            y = 20,
            w = 250,
            h = 50,
            state = "normal",
            text = "Back to rooms"
        },
        revive = {
            x = 300,
            y = 400,
            w = 200,
            h = 50,
            state = "normal",
            text = "Revive"
        },
    },
    room_buttons = {
        room_1 = {},
        room_2 = {},
        room_3 = {}
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

function getSkin(skin_id)
    local skin = {}
    if skin_id == 1 then
        skin.tank_up = resources.tank_up_1
        skin.tank_down = resources.tank_down_1
        skin.tank_left = resources.tank_left_1
        skin.tank_right = resources.tank_right_1
    elseif skin_id == 2 then
        skin.tank_up = resources.tank_up_2
        skin.tank_down = resources.tank_down_2
        skin.tank_left = resources.tank_left_2
        skin.tank_right = resources.tank_right_2
    elseif skin_id == 3 then
        skin.tank_up = resources.tank_up_3
        skin.tank_down = resources.tank_down_3
        skin.tank_left = resources.tank_left_3
        skin.tank_right = resources.tank_right_3
    elseif skin_id == 4 then
        skin.tank_up = resources.tank_up_4
        skin.tank_down = resources.tank_down_4
        skin.tank_left = resources.tank_left_4
        skin.tank_right = resources.tank_right_4
    else
        skin.tank_up = resources.tank_up_3
        skin.tank_down = resources.tank_down_3
        skin.tank_left = resources.tank_left_3
        skin.tank_right = resources.tank_right_3
    end

    return skin
end

function connectToServer(room_id)
    if game_state.name == "" then
        network.udp:settimeout(0)
        network.udp:setpeername(network.server_ip, network.server_port)
    end
    sendNetworkMessage({
        action = "join_room",
        player_id = network.player_id,
        room_name = room_id
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
    love.window.setTitle("Tetanki - Lobby")
    love.window.setMode(800, 600)
    resources.lobby_music:setLooping(true)
    resources.game_music:setLooping(true)
    currentMusic = resources.lobby_music
    currentMusic:play()
end

function love.update(dt)
    -- Love is buggy!!!! This dt thing is not reliable

    if not lobby.choosing_room or game_state.name ~= "" then
        if network.player_speed.vx ~= 0 or network.player_speed.vy ~= 0  and network.is_alive then
            local new_position = network.player_position
            new_position.x = network.player_position.x + (network.player_speed.vx * dt)
            new_position.y = network.player_position.y + (network.player_speed.vy * dt)
            network.player_position = new_position
        end
    
    
        -- this is spam, but lets think it is OK :)
        if lobby.show_lobby == false and network.player_position ~= game_state.players[network.player_id].player_position then
            sendNetworkMessage({
                action = "move",
                player_id = network.player_id,
                position = network.player_position,
                direction = network.player_direction
            })
        end
        
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

end

function handleNetworkMessage(msg)
    if msg.action == "update_state" then
        -- Print "Update state"
        game_state = msg.game_state
        -- Check if we are in players, but the waiting_room is empty - this means game started
        if game_state.game_started then
            lobby.show_lobby = false
            lobby.choosing_room = false
            if currentMusic ~= resources.game_music then
                love.window.setTitle('Tetanki - FIGHT!')
                network.player_skin = game_state.players[network.player_id].skin
                network.player_position = game_state.players[network.player_id].position
                currentMusic:stop()
                currentMusic = resources.game_music
                currentMusic:play()
            end
        else
            game_state.players[network.player_id].position = network.player_position
        end

        if msg.game_state.players[network.player_id].hp == 0 then
            network.is_alive = false
            network.player_speed.vx = 0
            network.player_speed.vy = 0
        else
            network.is_alive = true
        end
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
    if lobby.choosing_room then
        drawRoomChoice()
    else
        if lobby.show_lobby then
            drawLobby()
        else
            drawGame()
        end
    end
end

-- Game related

function drawTank(x, y, hp, id, direction, skin_id)

    -- Draw tank
    if hp == 0 then
        love.graphics.setColor(1, 0.1, 0.1)
    else
        love.graphics.setColor(1, 1, 1)
    end

    local skin = getSkin(skin_id)

    local img = skin.tank_up
    if direction == "down" then
        img = skin.tank_down
    elseif direction == "left" then
        img = skin.tank_left
    elseif direction == "right" then
        img = skin.tank_right
    end
    -- Tank image is 150x150, but the tank is just 50x50 (approx). So we need to draw it at the center of the tank.
    love.graphics.draw(img, x - 25, y - 25)

    -- Print player ID on top of the tank
    love.graphics.setFont(resources.font_tank)
    love.graphics.setColor(1, 1, 1)
    love.graphics.printf(id, x - 100, y - 60, 200, "center")

    -- Draw HP bar
    love.graphics.setColor(0, 1, 0)
    local hp_width = 100 * (hp / 100)
    love.graphics.rectangle("fill", x - 50, y + 30, hp_width, 10)
    love.graphics.setColor(1, 1, 1)
    love.graphics.rectangle("line", x - 50, y + 30, 100, 10)
end

function drawPlayer(skin_id)
    -- Draw player tank
    if (network.is_alive) then
        love.graphics.setColor(1, 1, 1)
    else
        love.graphics.setColor(1, 0.1, 0.1)
    end

    local skin = getSkin(skin_id)

    local img = skin.tank_up
    if network.player_direction == "down" then
        img = skin.tank_down
    elseif network.player_direction == "left" then
        img = skin.tank_left
    elseif network.player_direction == "right" then
        img = skin.tank_right
    end
    love.graphics.draw(img, network.player_position.x - 25, network.player_position.y - 25)
end

function drawGame()
    love.graphics.setColor(1, 1, 1)
    love.graphics.draw(resources.background, 0, 0)
    for player_id, player in pairs(game_state.players) do
        if player_id == network.player_id then
            drawPlayer(network.player_skin)
        else
            drawTank(player.position.x, player.position.y, player.hp, player_id, player.direction, player.skin)
        end
    end

    for _, bullet in pairs(game_state.bullets) do
        -- file = io.open("debug.log", "a")
        -- file:write(json.encode(bullet))
        -- file:close()

        love.graphics.setColor(1, 1, 1)
        love.graphics.circle("fill", bullet.position.x, bullet.position.y, 5)
    end

    if not network.is_alive then
        love.graphics.setColor(1, 0, 0)
        love.graphics.setFont(resources.font_title)
        love.graphics.printf("GAME OVER", 0, love.graphics.getHeight() / 2, love.graphics.getWidth(), "center")
        drawButton(lobby.buttons.revive)
    end

    -- Draw healthbar on the bottom of the screen
    local hp = game_state.players[network.player_id].hp
    local bar_width = (hp / 100) * love.graphics.getWidth()
    love.graphics.setColor(1, 0, 0)
    love.graphics.rectangle("fill", 0, love.graphics.getHeight() - 10, love.graphics.getWidth(), 10)
    love.graphics.setColor(0, 1, 0)
    love.graphics.rectangle("fill", 0, love.graphics.getHeight() - 10, bar_width, 10)
end

function love.keypressed(key)
    if network.is_alive then
        if key == "w" then
            network.player_direction = "up"
            network.player_speed.vy = -200
            network.player_speed.vx = 0
        elseif key == "a" then
            network.player_direction = "left"
            network.player_speed.vx = -200
            network.player_speed.vy = 0
        elseif key == "s" then
            network.player_direction = "down"
            network.player_speed.vy = 200
            network.player_speed.vx = 0
        elseif key == "d" then
            network.player_direction = "right"
            network.player_speed.vx = 200
            network.player_speed.vy = 0
        elseif key == "space" then
            if os.time() - network.last_bullet_fired_ts >= 1 then
                network.last_bullet_fired_ts = os.time()
                sendNetworkMessage({
                    action = "shoot",
                    player_id = network.player_id
                }) 
            end
        end
    end
end

function love.keyreleased(key)
    if network.is_alive then
        checkUnreleasedKeys(key)
    end
end

--Checks if should update the direction to the key that has been pressed before
function checkUnreleasedKeys(key)
    if love.keyboard.isDown('w') and key ~= 'w' then
        network.player_direction = "up"
        network.player_speed.vy = -200
        network.player_speed.vx = 0
    elseif love.keyboard.isDown('a') and key ~= 'a' then
        network.player_direction = "left"
        network.player_speed.vx = -200
        network.player_speed.vy = 0
    elseif love.keyboard.isDown('s') and key ~= 's' then
        network.player_direction = "down"
        network.player_speed.vy = 200
        network.player_speed.vx = 0
    elseif love.keyboard.isDown('d') and key ~= 'd' then
        network.player_direction = "right"
        network.player_speed.vx = 200
        network.player_speed.vy = 0
    else
        network.player_speed.vx = 0
        network.player_speed.vy = 0
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


function drawRoomChoice()
    love.graphics.setColor(1, 1, 1)
    love.graphics.print("Choose room - Player ID: " .. network.player_id, 20, 20)

    y = 60
    love.graphics.print("Available rooms:", 20, y)
    y = y + 30
    for i=1, 3 do
        local room_button = {
            x = 40,
            y = y,
            w = 200,
            h = 50,
            state = "normal",
            text = string.format("room_%d", i)
        }
        drawButton(room_button)
        if i == 1 then
            lobby.room_buttons.room_1 = room_button
        elseif i == 2 then
            lobby.room_buttons.room_2 = room_button
        else
            lobby.room_buttons.room_3 = room_button
        end
        y = y + 60
    end
end

function drawLobby()
    love.graphics.setColor(1, 1, 1)
    love.graphics.print("Lobby - Player ID: " .. network.player_id, 20, 20)

    -- Draw players list
    local y = 60
    love.graphics.print(string.format("Players in %s:", game_state.name), 20, y)
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
    drawButton(lobby.buttons.back)
    if not lobby.ready then
        drawButton(lobby.buttons.ready)
    end
    if allPlayersReady() then
        drawButton(lobby.buttons.start)
    end
end

function love.mousemoved(x, y)
    if lobby.show_lobby and not lobby.choosing_room then
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
        if lobby.choosing_room then
            for button_num, button in pairs(lobby.room_buttons) do
                if isPointInRect(x, y, button) then
                    button.state = "pressed"
                    resources.click_sound:play()
                    if game_state.name ~= button_num then
                        connectToServer(button_num)
                    end
                    lobby.choosing_room = false
                    lobby.ready = false
                    break
                end
            end
        -- Ready button
        else
            if isPointInRect(x, y, lobby.buttons.ready) then
                lobby.buttons.ready.state = "pressed"
                resources.click_sound:play()
                sendNetworkMessage({
                    action = "set_ready",
                    player_id = network.player_id
                })
                lobby.ready = not lobby.ready

                -- Start button
            elseif isPointInRect(x, y, lobby.buttons.back) then
                lobby.choosing_room = true
            elseif allPlayersReady() and isPointInRect(x, y, lobby.buttons.start) then
                lobby.buttons.start.state = "pressed"
                resources.click_sound:play()
                sendNetworkMessage({
                    action = "start_game",
                    player_id = network.player_id
                })
            end
        end
    elseif not network.is_alive then
        if isPointInRect(x, y, lobby.buttons.revive) then
            lobby.buttons.revive.state = "pressed"
            resources.click_sound:play()
            sendNetworkMessage({
                action = "revive",
                player_id = network.player_id
            })
            network.player_position = {x = math.random(100, 700), y = math.random(100, 500)}
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
    elseif not network.is_alive then
        if isPointInRect(x, y, lobby.buttons.revive) then
            lobby.buttons.revive.state = "hover"
        end
    end
end

function love.quit()
    sendNetworkMessage({
        action = 'leave',
        player_id = network.player_id
    })
end

function isPointInRect(x, y, rect)
    return x >= rect.x and x <= rect.x + rect.w and
        y >= rect.y and y <= rect.y + rect.h
end
