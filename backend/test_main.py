import queue
import pytest
import asyncio
from fastapi.testclient import TestClient
from main import app
import starlette.websockets
from starlette.testclient import WebSocketTestSession
import time
import json

client = TestClient(app)


def test_login():
    response = client.post(
        "/login", data={"username": "user1", "password": "password1"}
    )
    assert response.status_code == 200
    assert "__access_token__" in response.json()


def test_login_wrong_password():
    client.post("/login", data={"username": "user1", "password": "password1"})

    response = client.post(
        "/login", data={"username": "user1", "password": "wrongpass"}
    )
    assert response.status_code == 422


def test_login_again():
    first = client.post("/login", data={"username": "user2", "password": "password2"})

    second = client.post("/login", data={"username": "user2", "password": "password2"})

    assert first.json()["__access_token__"] != second.json()["__access_token__"]

async def _asgi_receive(session: WebSocketTestSession, timeout:float|None = None):
    _start = time.time()
    while session._send_queue.empty():
        await asyncio.sleep(0.1)
        if timeout and (time.time() > _start + timeout):
            raise asyncio.TimeoutError
    
    return session._send_queue.get()

async def receive_json(session, timeout:float|None=None):
    message = await _asgi_receive(session, timeout)
    # print("Message:", message)
    if isinstance(message, BaseException):
        raise message
    session._raise_on_close(message)
    text = message["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def paused_receive_json(session: WebSocketTestSession, timeout:float|None=None, cycle_timeout: float=1):
    _start = time.time()
    while timeout is None or (time.time() < _start + timeout):
        try:
            response = await receive_json(session, timeout=cycle_timeout)
            print("Received!")
            return response
        except queue.Empty:
            await asyncio.sleep(0.1)
        # except starlette.websockets.WebSocketDisconnect:
        #     break


@pytest.mark.asyncio
async def test_websocket_auth():
    response = client.post("/login", data={"username": "Ada", "password": "Ada_pass"})
    token = response.json()["__access_token__"]
    with pytest.raises(starlette.websockets.WebSocketDisconnect):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"message": "hello"})
            response = await receive_json(websocket)
            assert False

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(token)
        websocket.send_json({"message": "hello"})

        response = await receive_json(websocket)

        assert response == {"message": "hello"}


@pytest.mark.asyncio
async def test_broadcast():
    names = ["Ada", "Bert", "Carl"]
    clients = [TestClient(app) for _ in names]
    tokens = [
        client.post(
            "/login", data={"username": name, "password": f"{name}_pass"}
        ).json()["__access_token__"]
        for name, client in zip(names, clients)
    ]
    responses = set()

    async def foo(name, client, token):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(token)
            await asyncio.sleep(0.5)
            websocket.send_json({"sender": f"{name}"})
            
            while True:
                try:
                    response = await receive_json(websocket, timeout=1)
                    responses.add( (name, response["sender"]) )
                except queue.Empty:
                    await asyncio.sleep(0.1)
                except (starlette.websockets.WebSocketDisconnect, asyncio.TimeoutError):
                    break

    await asyncio.gather(*[foo(name, client, token) for name, client, token in zip(names, clients, tokens)])
    assert responses == { (receiver, sender) for receiver in names for sender in names }
