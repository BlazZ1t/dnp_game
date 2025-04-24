AnimEight = require('lib.anim8')
Camera = require('lib.camera')
local socket = require('socket')
local udp
local gameState = {}

local cam = Camera()

function love.conf(t)
    t.window.vsync = 1
end



function love.load()
    love.window.setMode(0, 0)
    love.graphics.setDefaultFilter("nearest", "nearest")
    udp = socket.udp()
    udp:settimeout(0)
    upd:setpeername('127.0.0.1', 9999)
        
end

function love.update(dt)
    
end

function love.draw()
    
end
