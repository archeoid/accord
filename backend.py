import asyncio
import websockets
import json
from aiohttp import web
from os import path

class Event:
    def __init__(self):
        self.type = "none"

class User:
    def __init__(self, username):
        self.username = "user"
        self.nickname = "Username"
        self.pfp = "cdn/default.png"
        self.password = "password"

async def handle_index(request):
    token = None
    if 'token' in request.cookies:
        token = request.cookies['token']
    if(token == None):
        return web.FileResponse('./login.html')
    else:
        return web.FileResponse('./chat.html')

async def error_middleware(request, handler):
    try:
        response = await handler(request)
        if response.status != 404:
            return response
        message = response.message
    except Exception as ex:
        pass
    return web.FileResponse('./404.html')

class Server:
    def __init__(self, ip, http_port, websocket_port=8081):
        self.ip = ip
        self.http_port = http_port
        self.websocket_port = websocket_port
        self.users = {}
        self.clients = {}
        self.id_set = list(range(1000)) #probably should remove the hard cap

        self.app = web.Application(middlewares=[error_middleware])
        self.app.add_routes([web.get('/', handle_index),
        web.static('/cdn', "cdn"),
        web.static('/css', "css")])
        self.runner = web.AppRunner(self.app)

        asyncio.run(self.run())

    async def run(self):
        #start aiohttp
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.ip, self.http_port)
        await self.site.start()
        #start websocket
        async with websockets.serve(self.client, self.ip, self.websocket_port):
            await asyncio.Future()

    async def client(self, websocket, path):
        id = self.id_set.pop()
        print(f"connected: {id}")
        self.clients[id] = websocket
        try:
            while True:
                raw = await websocket.recv()
                msg = json.loads(raw)
                await self.handler(id, msg)
        except Exception as e:
            print(f"error ({str(type(e).__name__)}): {str(e)}")
            pass
        print(f"disconnect: {id}")
        self.clients.pop(id)
        self.id_set += [id]
       
    def login(self, username, password):
        if username in self.users:
            if password == self.users[username].password:
                return True
            else:
                return False
        else:
            u = User(username)
            u.password = password
            u.nickname = username
            self.users[username] = u
            return True

    def verify(self, token, username):
        return True
    
    async def message(self, username, content):
        print("message: ", username, content)
        #todo: parse content for other actions here (/username X) etc
        out = {'event': 'broadcast', 'username': username, 'content': content}
        for id in self.clients:
            await self.clients[id].send(json.dumps(out))


    async def handler(self, id, msg):
        print("event: ", msg['event'])
        username = msg['username']
        event = msg['event']

        #handle login
        if(event == 'login'):
            if self.login(username, password=""):
                out = {"event": "login-success", 'token': username} #todo: derive an actual token
            else:
                out = {"event": "login-fail", 'fail': "password"}
            await self.clients[id].send(json.dumps(out))
            return

        #every non-login event needs to have a valid token
        token = msg['token']
        if not self.verify(token, username): #todo: actually verify token
            await self.clients[id].send(json.dumps({'event': 'validation-failure'}))
            return
        
        #handle regular events
        if(event == "send"):
            await self.message(username, msg['content'])

s = Server("localhost", 8000)
