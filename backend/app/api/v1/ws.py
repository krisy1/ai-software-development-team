from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.worker.events import get_redis

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/projects/{project_id}/ws")
async def project_events(websocket: WebSocket, project_id: str) -> None:
    """WebSocket endpoint for real-time project event streaming.

    Subscribes to the project's Redis pub/sub channel and forwards
    events to the connected client as JSON messages.
    """
    await websocket.accept()
    channel = f"project:{project_id}:events"
    logger.info(
        "websocket_connected",
        project_id=project_id,
        channel=channel,
    )

    try:
        redis_conn = await get_redis()
        pubsub = redis_conn.pubsub()
        async with pubsub as p:
            await p.subscribe(channel)
            async for message in p.listen():
                if message["type"] != "message":
                    continue
                try:
                    await websocket.send_text(message["data"])
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "websocket_error",
            project_id=project_id,
            error=str(exc),
        )
    finally:
        logger.info(
            "websocket_disconnected",
            project_id=project_id,
        )
