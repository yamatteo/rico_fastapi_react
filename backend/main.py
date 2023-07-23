import asyncio
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import auth
except:
    import backend.auth as auth

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket] = {}
        self.background_tasks = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        try:
            auth_message = await asyncio.wait_for(websocket.receive_text(), 1)
            user = auth.get_user_from_token(auth_message)
            name = user["name"]
            self.active_connections[name] = websocket
            return name
        except asyncio.TimeoutError:
            await websocket.close(code=1000, reason="Authentication error: waiting for __access_token__ timeout.")
            raise HTTPException(status_code=422, detail=f"Authentication error: waiting for __access_token__ timeout.")
        except auth.AuthenticationError as err:
            await websocket.close(code=1000, reason=f"Authentication error: {err}")
            raise HTTPException(status_code=422, detail=f"Authentication error: {err}")


    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def _send(self, data, websocket: WebSocket, timeout: float|None=None):
        coro =  websocket.send_json(data)
        if timeout:
            await asyncio.wait_for(coro, timeout)
        else:
            await coro

    async def _repeat_send(self, data, websocket: WebSocket, timeout: float|None=None):
        while True:
            try:
                await self._send(data, websocket, timeout=timeout)
                return
            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)

    async def narrowcast(self, data, websocket: WebSocket, timeout: float|None=None, cycle_timeout: float=1):
        coro =  self._repeat_send(data, websocket, timeout=cycle_timeout)
        if timeout:
            await asyncio.wait_for(coro, timeout)
        else:
            await coro

    async def broadcast(self, data, timeout:float|None = None, cycle_timeout: float=1):
        for websocket in self.active_connections.values():
            task = asyncio.create_task(self.narrowcast(data, websocket, timeout=timeout, cycle_timeout=cycle_timeout))

            # Add task to the set. This creates a strong reference.
            self.background_tasks.add(task)

            # To prevent keeping references to finished tasks forever,
            # make each task remove its own reference from the set after
            # completion:
            task.add_done_callback(self.background_tasks.discard)


manager = ConnectionManager()

@app.post("/login")
async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    try:
        return auth.login_or_signup(username, password)
    except auth.AuthenticationError as err:
        raise HTTPException(status_code=422, detail=f"Authentication error:{err}")

@app.websocket("/ws") 
async def websocket_endpoint(websocket: WebSocket):
    name = await manager.connect(websocket)

    async for message in websocket.iter_json():
        await manager.broadcast(message, timeout=5)
        

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)