AnimEight = require('lib.anim8')
Camera = require('lib.camera')
local Player = require('entities.player')
local socket = require('socket')
local udp
local gameState = {}

local cam = Camera()

function love.conf(t)
    t.window.vsync = 1
end



function love.load()
    udp = socket.udp()
    udp:settimeout(0)
    udp:setpeername("127.0.0.1", 9000)
    -- os.execute("python ../python_side/client.py")

    love.window.setMode(0, 0)
    love.graphics.setDefaultFilter("nearest", "nearest")

    gameState.current = 'login'
    gameState.playerIdInput = ''
end

function love.textinput(t)
    if gameState.current == 'login' then
        gameState.playerIdInput = gameState.playerIdInput .. t
    end
end

function love.keypressed(key)
    if gameState.current == "login" then
        if key == "backspace" then
            local byteoffset = utf8.offset(gameState.playerIdInput, -1)
            if byteoffset then
                gameState.playerIdInput = string.sub(gameState.playerIdInput, 1, byteoffset - 1)
            end
        elseif key == "return" then
            if udp and #gameState.playerIdInput > 0 then
                local loginMsg = {
                    player_id = gameState.playerIdInput,
                    action = "join_room"
                }
                local json = require("lib.dkjson")
                local message = json.encode(loginMsg)
                udp:send(message)
                gameState.current = "waiting"
            end
        end
    end
    
end

function love.update(dt)
    
end

function love.draw()
    if gameState.current == 'login' then
        love.graphics.print('Enter your Player ID', 100, 100)
        love.graphics.print(gameState.playerIdInput, 100, 300)
    end
end
