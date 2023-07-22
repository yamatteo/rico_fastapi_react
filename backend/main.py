from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import auth
import asyncio
import starlette.websockets

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = []

@app.post("/login")
async def login(username: str, password: str):
    return auth.login_or_signup(username, password)

@app.websocket("/ws") 
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    while True:
        try:
            data, user = await auth.receive_json(websocket)
        except (auth.AuthenticationError, starlette.websockets.WebSocketDisconnect):
            break
        for connection in active_connections: 
            await asyncio.wait_for(connection.send_json(data), 5)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)