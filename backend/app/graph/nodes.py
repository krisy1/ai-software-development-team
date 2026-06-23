from __future__ import annotations

from datetime import datetime, timezone

from app.agents import registry as agent_registry_module
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.graph.state import GraphState
from app.graph.validation import validate_artifact

logger = get_logger(__name__)

# Mapping of agent → (step_name, state_artifact_key) for skip logic
_SKIP_MAP: dict[str, tuple[str, str]] = {
    "requirements": ("requirements", "requirements"),
    "architect": ("architecture", "architecture"),
    "developer": ("development", "source_code"),
    "code_review": ("code_review", "review_report"),
    "tester": ("testing", "test_suite"),
    "documentation": ("documentation", "documentation"),
}


def _should_skip(state: GraphState, agent_name: str) -> bool:
    """Check if this agent step should be skipped during resume.

    When resuming from a checkpoint, completed steps that already
    have artifacts are skipped so the pipeline fast-forwards to
    the first uncompleted step.
    """
    if not state.get("resume_mode", False):
        return False
    entry = _SKIP_MAP.get(agent_name)
    if entry is None:
        return False
    step_name, artifact_key = entry
    return step_name in state.get("completed_steps", []) and state.get(artifact_key) is not None


def _get_registry():
    reg = agent_registry_module.registry
    if reg is None:
        raise AppException("Agent registry not initialized. Call init_registry() during startup.")
    return reg


def _save_step_checkpoint(state: GraphState, agent_name: str) -> None:
    """Persist a checkpoint to disk after every agent step.

    Saves full graph state, execution logs, and generated files
    so the workflow can be resumed from any point.
    """
    from app.services.storage_service import storage_service

    try:
        storage_service.save_checkpoint(
            project_id=state["project_id"],
            state=state,
            description=f"Step completed: {agent_name}",
        )

        execution_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "status": state.get("status", "unknown"),
            "revision": state.get("revision", 0),
            "completed_steps": state.get("completed_steps", []),
            "pending_steps": state.get("pending_steps", []),
            "error_count": len(state.get("errors", [])),
            "warning_count": len(state.get("warnings", [])),
        }
        storage_service.save_execution_log(state["project_id"], execution_log)
    except Exception as e:
        logger.warning("step_checkpoint_failed", agent=agent_name, error=str(e))


async def requirements_node(state: GraphState) -> dict:
    """Node: Requirements Agent — produces the SRS document."""
    logger.info("node:requirements_agent", project_id=state["project_id"])
    if _should_skip(state, "requirements"):
        logger.info("requirements_agent skipped (resume)")
        return {"current_agent": "requirements"}
    agent = _get_registry().get_agent("requirements")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("requirements", updates.get("requirements"))
        if errors:
            logger.warning("requirements_validation_issues", errors=errors)
        updates["completed_steps"] = ["requirements"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "requirements")
        return updates
    except Exception as e:
        logger.error("requirements_node_failed", error=str(e))
        return _error_updates(state, "requirements", str(e))


async def architect_node(state: GraphState) -> dict:
    """Node: Architect Agent — produces the architecture design."""
    logger.info("node:architect_agent", project_id=state["project_id"])
    if _should_skip(state, "architect"):
        logger.info("architect_agent skipped (resume)")
        return {"current_agent": "architect"}
    agent = _get_registry().get_agent("architect")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("architect", updates.get("architecture"))
        if errors:
            logger.warning("architecture_validation_issues", errors=errors)
        updates["completed_steps"] = ["architecture"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "architect")
        return updates
    except Exception as e:
        logger.error("architect_node_failed", error=str(e))
        return _error_updates(state, "architecture", str(e))


async def developer_node(state: GraphState) -> dict:
    """Node: Developer Agent — produces source code.

    If this is a rework iteration (triggered by code review),
    the existing review_report is passed as context so the
    developer can address specific feedback.
    """
    logger.info(
        "node:developer_agent",
        project_id=state["project_id"],
        rework=state.get("review_report") is not None,
    )
    # Skip during resume; do NOT skip during rework (resume_mode is False in rework)
    if _should_skip(state, "developer"):
        logger.info("developer_agent skipped (resume)")
        return {"current_agent": "developer"}
    agent = _get_registry().get_agent("developer")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("developer", updates.get("source_code"))
        if errors:
            logger.warning("developer_validation_issues", errors=errors)
        if "completed_steps" not in updates:
            updates["completed_steps"] = ["development"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "developer")
        return updates
    except Exception as e:
        logger.error("developer_node_failed", error=str(e))
        return _error_updates(state, "development", str(e))


async def code_review_node(state: GraphState) -> dict:
    """Node: Code Review Agent — reviews source code quality.

    Increments review_attempts counter. Routes to developer
    if score is below threshold in the edge function.
    """
    logger.info(
        "node:code_review_agent",
        project_id=state["project_id"],
        attempt=state.get("review_attempts", 0) + 1,
    )
    if _should_skip(state, "code_review"):
        logger.info("code_review_agent skipped (resume)")
        return {"current_agent": "code_review"}
    agent = _get_registry().get_agent("code_review")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("code_review", updates.get("review_report"))
        if errors:
            logger.warning("code_review_validation_issues", errors=errors)
        updates["review_attempts"] = state.get("review_attempts", 0) + 1
        updates["completed_steps"] = ["code_review"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "code_review")
        return updates
    except Exception as e:
        logger.error("code_review_node_failed", error=str(e))
        return _error_updates(state, "code_review", str(e))


async def tester_node(state: GraphState) -> dict:
    """Node: Tester Agent — produces test suite."""
    logger.info("node:tester_agent", project_id=state["project_id"])
    if _should_skip(state, "tester"):
        logger.info("tester_agent skipped (resume)")
        return {"current_agent": "tester"}
    agent = _get_registry().get_agent("tester")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("tester", updates.get("test_suite"))
        if errors:
            logger.warning("tester_validation_issues", errors=errors)
        updates["completed_steps"] = ["testing"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "tester")
        return updates
    except Exception as e:
        logger.error("tester_node_failed", error=str(e))
        return _error_updates(state, "testing", str(e))


async def documentation_node(state: GraphState) -> dict:
    """Node: Documentation Agent — produces technical documentation."""
    logger.info("node:documentation_agent", project_id=state["project_id"])
    if _should_skip(state, "documentation"):
        logger.info("documentation_agent skipped (resume)")
        return {"current_agent": "documentation"}
    agent = _get_registry().get_agent("documentation")

    try:
        updates = await agent.process(state)
        errors = validate_artifact("documentation", updates.get("documentation"))
        if errors:
            logger.warning("documentation_validation_issues", errors=errors)
        updates["completed_steps"] = ["documentation"]
        merged = {**state, **updates}
        _save_step_checkpoint(merged, "documentation")
        return updates
    except Exception as e:
        logger.error("documentation_node_failed", error=str(e))
        return _error_updates(state, "documentation", str(e))


async def validate_input_node(state: GraphState) -> dict:
    """Node: Validate the initial input before pipeline execution.

    During resume (``resume_mode=True``), skips validation since the
    state was already validated on the initial run.
    """
    logger.info("node:validate_input", project_id=state["project_id"])

    if state.get("resume_mode", False):
        logger.info("input validation skipped (resume)")
        return {"status": "running", "revision": state["revision"]}

    if not state["idea"] or len(state["idea"].strip()) < 10:
        error_msg = "Input idea must be at least 10 characters"
        logger.error("input_validation_failed", error=error_msg)
        return {
            "status": "failed",
            "errors": [{"agent": "validator", "message": error_msg}],
            "revision": state["revision"] + 1,
        }

    # Mark requirements as the next pending step
    return {
        "status": "running",
        "revision": state["revision"] + 1,
    }


async def persistence_node(state: GraphState) -> dict:
    """Node: Final state — persist artifacts, save checkpoints, and mark complete."""
    from datetime import datetime, timezone

    logger.info("node:persistence", project_id=state["project_id"])

    try:
        from app.services.storage_service import storage_service

        # Save full-state checkpoint to disk
        storage_service.save_checkpoint(
            project_id=state["project_id"],
            state=state,
            description="Pipeline complete",
        )

        # Save execution log for the finalization step
        storage_service.save_execution_log(
            state["project_id"],
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "persistence",
                "status": "completed",
                "revision": state.get("revision", 0),
                "completed_steps": state.get("completed_steps", []),
                "pending_steps": [],
                "error_count": len(state.get("errors", [])),
                "warning_count": len(state.get("warnings", [])),
            },
        )

        # Persist generated source code to disk
        source = state.get("source_code")
        if source and isinstance(source, dict):
            files = source.get("files", [])
            if files:
                storage_service.save_generated_code(
                    project_id=state["project_id"],
                    files=files,
                    revision=state.get("revision", 1),
                )

        # Save project manifest
        manifest = {
            "project_id": state["project_id"],
            "status": "completed",
            "revision": state.get("revision", 0),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": {
                k: v is not None
                for k, v in state.items()
                if k in ("requirements", "architecture", "source_code", "test_suite", "documentation", "review_report")
            },
        }
        storage_service.save_manifest(state["project_id"], manifest)

    except Exception as e:
        logger.warning("persistence_node_disk_failed", error=str(e))

    summary = {
        "agent": "persistence",
        "artifacts": {
            k: v is not None
            for k, v in state.items()
            if k in ("requirements", "architecture", "source_code", "test_suite", "documentation", "review_report")
        },
        "total_tokens": sum(
            t.get("total_tokens", 0) for t in state.get("token_usage", [])
        ),
    }

    return {
        "status": "completed",
        "end_time": datetime.now(timezone.utc).isoformat(),
        "current_agent": None,
        "agent_results": [summary],
        "revision": state["revision"] + 1,
    }


async def error_node(state: GraphState) -> dict:
    """Node: Handle unrecoverable pipeline errors."""
    from datetime import datetime, timezone

    logger.error(
        "node:error_handler",
        project_id=state["project_id"],
        errors=state["errors"],
    )

    return {
        "status": "failed",
        "end_time": datetime.now(timezone.utc).isoformat(),
        "current_agent": None,
        "revision": state["revision"] + 1,
    }


def _error_updates(state: GraphState, step: str, error_msg: str) -> dict:
    """Build error state updates for a failed node."""
    return {
        "errors": [{"step": step, "message": error_msg, "agent": state.get("current_agent")}],
        "status": "failed",
        "current_agent": None,
        "revision": state["revision"] + 1,
    }
