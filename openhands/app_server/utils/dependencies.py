import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from openhands.app_server.config import get_global_config
from openhands.app_server.types import AppMode

_SESSION_API_KEY = os.getenv('SESSION_API_KEY')
_SESSION_API_KEY_HEADER = APIKeyHeader(name='X-Session-API-Key', auto_error=False)


def check_session_api_key(
    request: Request,
    session_api_key: str | None = Depends(_SESSION_API_KEY_HEADER),
):
    """Check the session API key and throw an exception if incorrect.

    A valid basic-auth session cookie (oh_auth) is accepted as an alternative
    so that browser requests authenticated via the login form pass this check
    even when SESSION_API_KEY is also set.
    """
    # Accept a valid basic-auth session cookie as an alternative credential
    from openhands.app_server.auth.basic_auth_service import (
        COOKIE_NAME,
        ENABLED,
        verify_token,
    )

    if ENABLED and verify_token(request.cookies.get(COOKIE_NAME)):
        return

    if session_api_key != _SESSION_API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)


def get_dependencies() -> list[Depends]:
    result = []
    if _SESSION_API_KEY:
        result.append(Depends(check_session_api_key))
    elif get_global_config().app_mode == AppMode.SAAS:
        # This merely lets the OpenAPI Docs know that an X-Session-API-Key can be
        # used for security - it does not fail if the header is not provided
        # (Allowing cookies to also be used)
        result.append(Depends(APIKeyHeader(name='X-Access-Token', auto_error=False)))
    return result
