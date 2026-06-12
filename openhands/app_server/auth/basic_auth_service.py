"""Basic auth gate using OPENHANDS_BASIC_AUTH_USER / OPENHANDS_BASIC_AUTH_PASSWORD.

Session tokens are HMAC-signed with OH_SECRET_KEY (falls back to JWT_SECRET).
"""

import base64
import hashlib
import hmac
import os
import time

_USER = os.getenv('OPENHANDS_BASIC_AUTH_USER', '')
_PASSWORD = os.getenv('OPENHANDS_BASIC_AUTH_PASSWORD', '')
_SECRET = (
    os.getenv('OH_SECRET_KEY') or os.getenv('JWT_SECRET') or 'change-me-set-OH_SECRET_KEY'
)

ENABLED = bool(_USER and _PASSWORD)
COOKIE_NAME = 'oh_auth'
TOKEN_TTL = 7 * 24 * 3600  # 7 days


def verify_credentials(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(_USER.encode(), username.encode())
    ok_pass = hmac.compare_digest(_PASSWORD.encode(), password.encode())
    return ok_user and ok_pass


def _sign(payload: str) -> str:
    return hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token() -> str:
    expires = str(int(time.time()) + TOKEN_TTL)
    sig = _sign(expires)
    raw = f'{expires}.{sig}'
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        # urlsafe_b64decode needs padding
        padded = token + '=' * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        expires_str, sig = raw.rsplit('.', 1)
        if not hmac.compare_digest(sig, _sign(expires_str)):
            return False
        return time.time() < float(expires_str)
    except Exception:
        return False
