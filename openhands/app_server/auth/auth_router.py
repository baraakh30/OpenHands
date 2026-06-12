"""Auth endpoints for the basic-auth gate."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openhands.app_server.auth.basic_auth_service import (
    COOKIE_NAME,
    ENABLED,
    TOKEN_TTL,
    create_token,
    verify_credentials,
    verify_token,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get('/api/auth/check')
async def auth_check(request: Request):
    """Return whether basic auth is required and whether the current session is valid."""
    if not ENABLED:
        return {'required': False, 'authenticated': True}
    token = request.cookies.get(COOKIE_NAME)
    return {'required': True, 'authenticated': verify_token(token)}


@router.post('/api/auth/login')
async def auth_login(body: LoginRequest):
    """Validate credentials and set a session cookie."""
    if not ENABLED:
        # Auth not configured — always succeed (no-op)
        response = JSONResponse({'ok': True})
        return response

    if not verify_credentials(body.username, body.password):
        return JSONResponse({'detail': 'Invalid credentials'}, status_code=401)

    token = create_token()
    response = JSONResponse({'ok': True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=TOKEN_TTL,
        httponly=True,
        samesite='lax',
        secure=False,  # set to True behind HTTPS proxy; Railway handles TLS termination
    )
    return response


@router.post('/api/auth/logout')
async def auth_logout():
    """Clear the session cookie."""
    response = JSONResponse({'ok': True})
    response.delete_cookie(COOKIE_NAME)
    return response
