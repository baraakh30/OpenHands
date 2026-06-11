"""Proxy router for agent server communication.

Routes /runtime/{port}/* requests to the local agent server at localhost:{port}.
This allows browsers to reach agent servers (which run on internal ports) via
the app server's public hostname.
"""

import asyncio
import logging

import aiohttp
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

_logger = logging.getLogger(__name__)

# Only allow proxying to ports in this range (agent servers start at 8000)
_MIN_PORT = 8000
_MAX_PORT = 65535

router = APIRouter()


def _validate_port(port: int) -> bool:
    return _MIN_PORT <= port <= _MAX_PORT


@router.api_route(
    '/runtime/{port}/{path:path}',
    methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'],
)
async def proxy_http(port: int, path: str, request: Request) -> Response:
    if not _validate_port(port):
        return Response(content='Invalid port', status_code=400)

    target_url = f'http://localhost:{port}/{path}'
    query_string = request.url.query
    if query_string:
        target_url += f'?{query_string}'

    body = await request.body()
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ('host', 'content-length', 'transfer-encoding')
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                data=body or None,
                timeout=aiohttp.ClientTimeout(total=60),
                allow_redirects=False,
            ) as resp:
                content = await resp.read()
                response_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower()
                    not in (
                        'transfer-encoding',
                        'content-encoding',
                        'content-length',
                    )
                }
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=response_headers,
                )
        except aiohttp.ClientError as exc:
            _logger.warning('HTTP proxy error for port %d path %s: %s', port, path, exc)
            return Response(content=f'Proxy error: {exc}', status_code=502)


@router.websocket('/runtime/{port}/sockets/events/{conversation_id}')
async def proxy_websocket(
    port: int, conversation_id: str, websocket: WebSocket
) -> None:
    if not _validate_port(port):
        await websocket.close(code=4000)
        return

    await websocket.accept()

    query_string = websocket.url.query
    target_url = f'ws://localhost:{port}/sockets/events/{conversation_id}'
    if query_string:
        target_url += f'?{query_string}'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                target_url,
                timeout=aiohttp.ClientWSTimeout(ws_connect=10),
            ) as ws_agent:

                async def forward_from_agent() -> None:
                    async for msg in ws_agent:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await websocket.send_text(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await websocket.send_bytes(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

                async def forward_from_client() -> None:
                    try:
                        while True:
                            data = await websocket.receive()
                            if data.get('type') == 'websocket.disconnect':
                                break
                            if 'text' in data and data['text'] is not None:
                                await ws_agent.send_str(data['text'])
                            elif 'bytes' in data and data['bytes'] is not None:
                                await ws_agent.send_bytes(data['bytes'])
                    except WebSocketDisconnect:
                        pass

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(forward_from_agent()),
                        asyncio.create_task(forward_from_client()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

    except aiohttp.ClientError as exc:
        _logger.warning(
            'WebSocket proxy error for conversation %s port %d: %s',
            conversation_id,
            port,
            exc,
        )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
