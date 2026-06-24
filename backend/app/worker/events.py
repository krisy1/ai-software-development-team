from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the shared async Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the shared Redis connection."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


class EventPublisher:
    """Publish events during agent execution for real-time streaming.

    Publishes to Redis pub/sub channels. The WebSocket handler
    subscribes to these channels to push updates to connected clients.
    """

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.channel = f"project:{project_id}:events"

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to the project's Redis pub/sub channel."""
        message = {
            "type": event_type,
            "project_id": self.project_id,
            "data": data,
        }
        serialized = json.dumps(message)
        try:
            redis_conn = await get_redis()
            await redis_conn.publish(self.channel, serialized)
        except Exception as exc:
            logger.debug(
                "redis_publish_failed",
                channel=self.channel,
                event_type=event_type,
                error=str(exc),
            )

    async def agent_started(self, agent_type: str) -> None:
        await self.publish("agent_started", {"agent_type": agent_type})

    async def agent_completed(
        self, agent_type: str, duration_ms: int, token_usage: dict[str, int]
    ) -> None:
        await self.publish(
            "agent_completed",
            {
                "agent_type": agent_type,
                "duration_ms": duration_ms,
                "token_usage": token_usage,
            },
        )

    async def agent_error(self, agent_type: str, error: str) -> None:
        await self.publish(
            "agent_error", {"agent_type": agent_type, "error": error}
        )

    async def artifact_generated(
        self, artifact_type: str, preview: str
    ) -> None:
        await self.publish(
            "artifact_generated",
            {"artifact_type": artifact_type, "preview": preview[:200]},
        )

    async def pipeline_started(self) -> None:
        await self.publish("pipeline_started", {})

    async def pipeline_completed(self, status: str, summary: dict[str, Any]) -> None:
        await self.publish("pipeline_completed", {"status": status, "summary": summary})

    async def pipeline_error(self, error: str) -> None:
        await self.publish("pipeline_error", {"error": error})
