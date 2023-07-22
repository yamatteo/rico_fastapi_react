"""
Provides authentication utilities for the application.

Generates salted password hashes and tokens for verifying user identity.
Manages a simple in-memory user database.
"""

import secrets
import hashlib

from fastapi import WebSocket

salt = secrets.token_hex(16)
active_users = {}


class AuthenticationError(Exception):
    """Custom exception raised on authentication failure."""

    pass


def hash_password(password: str) -> str:
    """Hashes a password with a random salt."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


def check_token(token: str) -> bool:
    """Checks if an access token is valid for a user."""
    try:
        username, token_hex = token.split("~")
        return active_users[username]["token_hex"] == token_hex
    except:
        return False


def get_user_from_token(token: str) -> dict:
    """Returns user data if token is valid, raises error otherwise."""
    if not check_token(token):
        raise AuthenticationError
    username, _ = token.split("~")
    return active_users[username]


def login_or_signup(username: str, password: str, **kwargs) -> dict:
    """Logs in user if exists, otherwise signs up new user."""
    user = active_users.get(username, None)
    hex = secrets.token_hex(16)
    hash = hash_password(password)
    if user and user["password_hash"] == hash:
        active_users[username] = dict(user, token_hex=hex, **kwargs)
    elif user:
        raise AuthenticationError("Username is taken, and password doesn't match.")
    else:
        active_users[username] = dict(password_hash=hash, token_hex=hex, **kwargs)
    return {"__access_token__": f"{username}~{hex}"}


async def receive_json(websocket: WebSocket) -> tuple[dict, dict]:
    """Receives JSON data from websocket, validates token, and returns data."""
    data: dict = await websocket.receive_json()
    token = data.pop("__access_token__")
    user = get_user_from_token(token)
    return data, user
