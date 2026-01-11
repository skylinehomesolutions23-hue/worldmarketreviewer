import time
import hashlib

SECRET = "super-secret-key-change-me"

def generate_token(username: str):
    payload = f"{username}:{int(time.time())}:{SECRET}"
    return hashlib.sha256(payload.encode()).hexdigest()

def verify(token: str):
    return token is not None and len(token) == 64
