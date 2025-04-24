local Player = {}

Player.__index = Player

function Player.new()
    local self = setmetatable({}, Player)
    --TODO: Add player stats
    return self
end



return Player