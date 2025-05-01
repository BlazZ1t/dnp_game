# Setup guide

## Easy way (only Windows)

1. Download the latest .exe file from github.com/BlazZ1t/dnp_game/releases/latest
2. Make sure you are on UniversityStudent WIFI network and contact t.me/blazz1t for running the server if you are unable to connect (unfortunately our server-host IP is imbeded into the .exe file)
2. Launch .exe file
3. Enjoy the game!

If you for any reason don't wish to bother yourself with step 2, watch below

## Hard way

Using your own server requires a little bit of setup
1. Find out your ip address and paste it into line 412 of server/server.py and line 7 in client/python_side/client.py
2. Install Love2D for your system on love2d.org (may require VPN)
3. Make sure to add installed LOVE folder to Path (on Windows). Check Love installation with ```love --version``` in terminal
4. Run server with ```python server/server.py``` on windows and ```python3 server/server.py``` on linux
5. Run python bridge with ```python client/python_side/client.py``` on Windows and ```python3 client/python_side/client.py``` on linux
6. In the terminal navigate into client/lua_side folder and execute ```love .```
7. If you wish to run more than one client on one PC, change ports in line 10 of client.py and line 54 of main.lua
8. Test and enjoy!