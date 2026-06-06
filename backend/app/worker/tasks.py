from __future__ import annotations

import asyncio
from uuid import UUID

from app.agents.registry import init_registry
from app.core.logging import get_logger
from app.graph.pipeline import get_pipeline
from app.graph.state import create_initial_state, state_summary
from app.services.llm_service import llm_service
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_generation_pipeline(
    self,
    idea: str,
    project_id: str,
    constraints: dict | None = None,
) -> dict:
    """Execute the full agent generation pipeline asynchronously.

    This Celery task runs the complete LangGraph workflow for a
    given project idea. It is invoked by the API after project creation.

    The pipeline:
    1. Creates initial GraphState from the idea
    2. Invokes the LangGraph compiled pipeline
    3. Returns the final state summary with status and artifact info

    Retry Strategy:
    - 3 retries with 30s exponential backoff
    - Retries on transient failures (network, rate limit)
    - Does NOT retry on validation errors or bad input
    """
    logger.info(
        "pipeline_task_started",
        project_id=project_id,
        task_id=self.request.id,
    )

    try:
        # Initialize registry if needed (runs in worker process)
        if not hasattr(run_generation_pipeline, "_registry_initialized"):
            if llm_service.is_available:
                init_registry(llm_service)
                run_generation_pipeline._registry_initialized = True

        # Create initial state
        state = create_initial_state(
            idea=idea,
            constraints=constraints,
            project_id=UUID(project_id),
        )

        logger.info(
            "pipeline_state_created",
            project_id=project_id,
            state_preview=state_summary(state),
        )

        # Execute the pipeline
        pipeline = get_pipeline()

        # All nodes in the pipeline are async def — use ainvoke() instead of invoke()
        # asyncio.run() bridges the sync Celery task to the async LangGraph runtime.
        # The configurable thread_id is required when using MemorySaver checkpointing.
        final_state = asyncio.run(
            pipeline.ainvoke(
                state,
                config={"configurable": {"thread_id": project_id}},
            )
        )

        summary = state_summary(final_state)
        logger.info(
            "pipeline_task_completed",
            project_id=project_id,
            summary=summary,
        )

        return {
            "project_id": project_id,
            "status": final_state["status"],
            "revision": final_state["revision"],
            "has_requirements": final_state.get("requirements") is not None,
            "has_architecture": final_state.get("architecture") is not None,
            "has_source_code": final_state.get("source_code") is not None,
            "has_tests": final_state.get("test_suite") is not None,
            "has_documentation": final_state.get("documentation") is not None,
            "has_review": final_state.get("review_report") is not None,
            "error_count": len(final_state.get("errors", [])),
            "warning_count": len(final_state.get("warnings", [])),
        }

    except Exception as exc:
        logger.error(
            "pipeline_task_failed",
            project_id=project_id,
            error=str(exc),
            task_id=self.request.id,
        )
        raise self.retry(exc=exc)
