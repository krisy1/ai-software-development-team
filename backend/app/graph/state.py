from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Optional, TypedDict
from uuid import UUID, uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


class GraphState(TypedDict):
    """Shared state schema for the LangGraph agent pipeline.

    Every agent reads from and writes to this state object.
    LangGraph merges returned dict updates into this state.

    Fields annotated with ``Annotated[list, operator.add]`` use
    a custom reducer that appends new items to the existing list
    rather than overwriting.
    """

    # === Input ===
    idea: str
    constraints: Optional[dict[str, Any]]

    # === Project Metadata ===
    project_id: str
    status: str  # ProjectStatus enum value as string
    current_agent: Optional[str]  # AgentType enum value as string
    errors: Annotated[list[dict[str, Any]], operator.add]
    warnings: Annotated[list[dict[str, Any]], operator.add]

    # === Generated Artifacts ===
    # Each artifact is stored as an optional dict (model_dump() of domain model)
    requirements: Optional[dict[str, Any]]
    architecture: Optional[dict[str, Any]]
    source_code: Optional[dict[str, Any]]
    test_suite: Optional[dict[str, Any]]
    documentation: Optional[dict[str, Any]]
    review_report: Optional[dict[str, Any]]

    # === Execution Tracking ===
    start_time: str
    end_time: Optional[str]
    revision: int
    token_usage: Annotated[list[dict[str, Any]], operator.add]
    agent_results: Annotated[list[dict[str, Any]], operator.add]

    # === Code Review Loop ===
    review_attempts: int
    max_review_attempts: int

    # === Resume Support ===
    resume_mode: bool  # True when state was loaded from a checkpoint for resumption

    # === Step Tracking ===
    completed_steps: Annotated[list[str], operator.add]
    pending_steps: Annotated[list[str], operator.add]


def create_initial_state(
    idea: str,
    constraints: Optional[dict[str, Any]] = None,
    project_id: Optional[UUID] = None,
    max_review_attempts: int = 3,
) -> GraphState:
    """Create the initial state for a new generation pipeline.

    Args:
        idea: The software idea to generate from.
        constraints: Optional constraints (tech stack, etc.).
        project_id: Optional UUID; auto-generated if not provided.
        max_review_attempts: Maximum code review → rework loops.

    Returns:
        A new GraphState dict ready for pipeline execution.
    """
    now = datetime.now(timezone.utc).isoformat()

    state: GraphState = {
        # Input
        "idea": idea,
        "constraints": constraints,
        # Metadata
        "project_id": str(project_id or uuid4()),
        "status": "pending",
        "current_agent": None,
        "errors": [],
        "warnings": [],
        # Artifacts (all None initially)
        "requirements": None,
        "architecture": None,
        "source_code": None,
        "test_suite": None,
        "documentation": None,
        "review_report": None,
        # Execution
        "start_time": now,
        "end_time": None,
        "revision": 0,
        "token_usage": [],
        "agent_results": [],
        # Review loop
        "review_attempts": 0,
        "max_review_attempts": max_review_attempts,
        # Resume
        "resume_mode": False,
        # Step tracking
        "completed_steps": [],
        "pending_steps": [
            "requirements",
            "architecture",
            "development",
            "code_review",
            "testing",
            "documentation",
        ],
    }
    return state


def state_summary(state: GraphState) -> dict[str, Any]:
    """Return a human-readable summary of the current state."""
    return {
        "project_id": state["project_id"],
        "status": state["status"],
        "current_agent": state["current_agent"],
        "revision": state["revision"],
        "errors": len(state["errors"]),
        "warnings": len(state["warnings"]),
        "completed_steps": state["completed_steps"],
        "pending_steps": state["pending_steps"],
        "has_requirements": state["requirements"] is not None,
        "has_architecture": state["architecture"] is not None,
        "has_source_code": state["source_code"] is not None,
        "has_tests": state["test_suite"] is not None,
        "has_docs": state["documentation"] is not None,
        "has_review": state["review_report"] is not None,
        "review_attempts": state.get("review_attempts", 0),
    }
