from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.logging import get_logger
from app.graph.edges import (
    route_after_code_review,
    route_after_documentation,
    route_after_development,
    route_after_requirements,
    route_after_architecture,
    route_after_testing,
    route_after_validation,
)
from app.graph.nodes import (
    architect_node,
    code_review_node,
    developer_node,
    documentation_node,
    error_node,
    persistence_node,
    requirements_node,
    tester_node,
    validate_input_node,
)
from app.graph.state import GraphState, state_summary

logger = get_logger(__name__)


def build_pipeline() -> StateGraph:
    """Construct the LangGraph StateGraph pipeline.

    The pipeline follows a sequential agent workflow with a feedback loop:

    ```
    START
      │
      ▼
    validate_input ──(failed)──▶ error_handler ──▶ END
      │
      ▼
    requirements_agent ──(failed)──▶ error_handler ──▶ END
      │
      ▼
    architect_agent ──(failed)──▶ error_handler ──▶ END
      │
      ▼
    developer_agent ──(failed)──▶ error_handler ──▶ END
      │
      ▼
    code_review_agent
      │
      ├──(score ≥ 6.0 OR max attempts)──▶ tester_agent
      │                                       │
      └──(score < 6.0 AND attempts remain)──▶ developer_agent (rework loop)
                                              │
                                              ▼
                                            tester_agent ──(failed)──▶ error_handler
                                              │
                                              ▼
                                            documentation_agent
                                              │
                                              ▼
                                            persistence_node ──▶ END
    ```

    Error Handling:
    - Every node is wrapped in try/except in nodes.py
    - Errors route to the central error_handler node
    - The error_handler marks the project as failed and terminates
    - Agent-level retries (2 retries) happen *inside* each agent via BaseAgent.process()
    - Network/API failures use tenacity exponential backoff in LLMService

    Code Review Feedback Loop:
    - After code review, if overall_score < 6.0 and attempts < max_attempts,
      the pipeline routes back to the developer with review context
    - The developer re-generates code addressing the review feedback
    - After max_attempts reached, proceeds to tester regardless of score

    State Transitions:
    - Each node returns a dict of field updates
    - LangGraph merges updates into shared state using reducers
    - errors/agent_results/token_usage use ``operator.add`` (appends)
    - All other fields are overwritten on each update
    """

    workflow = StateGraph(GraphState)

    # ── Register all nodes ──────────────────────────────────
    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("requirements_agent", requirements_node)
    workflow.add_node("architect_agent", architect_node)
    workflow.add_node("developer_agent", developer_node)
    workflow.add_node("code_review_agent", code_review_node)
    workflow.add_node("tester_agent", tester_node)
    workflow.add_node("documentation_agent", documentation_node)
    workflow.add_node("persistence_node", persistence_node)
    workflow.add_node("error_handler", error_node)

    # ── Define edges ────────────────────────────────────────
    workflow.set_entry_point("validate_input")

    # validate_input → requirements_agent OR error_handler
    workflow.add_conditional_edges(
        "validate_input",
        route_after_validation,
    )

    # Sequential agent chain
    # Each router returns the next node name or "error_handler"
    workflow.add_conditional_edges("requirements_agent", route_after_requirements)
    workflow.add_conditional_edges("architect_agent", route_after_architecture)
    workflow.add_conditional_edges("developer_agent", route_after_development)

    # Code review → developer (rework) OR tester OR error_handler
    workflow.add_conditional_edges("code_review_agent", route_after_code_review)

    # Tester → documentation OR error_handler
    workflow.add_conditional_edges("tester_agent", route_after_testing)

    # Documentation → persistence OR error_handler
    workflow.add_conditional_edges("documentation_agent", route_after_documentation)

    # Terminal edges
    workflow.add_edge("persistence_node", END)
    workflow.add_edge("error_handler", END)

    # ── Compile with checkpointing ──────────────────────────
    memory = MemorySaver()
    pipeline = workflow.compile(checkpointer=memory)

    logger.info("pipeline_compiled", nodes=list(workflow.nodes.keys()))
    return pipeline


# ── Checkpoint resumption ────────────────────────────────────────


def _clean_pending_steps(completed_steps: list[str]) -> list[str]:
    """Determine which steps remain after a set of completed steps."""
    all_steps = ["requirements", "architecture", "development", "code_review", "testing", "documentation"]
    return [s for s in all_steps if s not in completed_steps]


def resume_from_checkpoint(
    checkpoint_path: str,
    fresh_pipeline: bool = False,
) -> tuple[StateGraph, GraphState]:
    """Resume pipeline execution from a saved checkpoint.

    Loads the checkpoint, reconstructs the GraphState with ``resume_mode=True``,
    and returns a fresh pipeline + state ready for ``pipeline.invoke(state)``.

    Completed steps are automatically skipped (nodes are no-ops via
    ``_should_skip`` in ``nodes.py``). The pipeline fast-forwards to
    the first uncompleted step.

    Args:
        checkpoint_path: Path to a ``.json`` checkpoint file created by
            ``StorageService.save_checkpoint()``.
        fresh_pipeline: If True, builds a new pipeline instance instead
            of using the singleton. Use this to avoid cross-contamination
            from previous pipeline runs.

    Returns:
        A tuple of ``(pipeline, state)`` ready for ``pipeline.invoke(state)``.

    Raises:
        FileNotFoundError: If the checkpoint path does not exist.
    """
    from pathlib import Path

    from app.services.storage_service import storage_service

    path = Path(checkpoint_path)
    checkpoint = storage_service.load_checkpoint(path)
    raw_state = checkpoint.get("state", {})

    completed = raw_state.get("completed_steps", [])
    pending = _clean_pending_steps(completed)

    state: GraphState = {
        "idea": raw_state.get("idea", ""),
        "constraints": raw_state.get("constraints"),
        "project_id": raw_state.get("project_id", checkpoint.get("project_id", "unknown")),
        "status": "running",
        "current_agent": None,
        "errors": checkpoint.get("errors", raw_state.get("errors", [])),
        "warnings": checkpoint.get("warnings", raw_state.get("warnings", [])),
        "requirements": raw_state.get("requirements"),
        "architecture": raw_state.get("architecture"),
        "source_code": raw_state.get("source_code"),
        "test_suite": raw_state.get("test_suite"),
        "documentation": raw_state.get("documentation"),
        "review_report": raw_state.get("review_report"),
        "start_time": raw_state.get("start_time", checkpoint.get("timestamp")),
        "end_time": None,
        "revision": raw_state.get("revision", 0),
        "token_usage": checkpoint.get("token_usage", raw_state.get("token_usage", [])),
        "agent_results": raw_state.get("agent_results", []),
        "review_attempts": raw_state.get("review_attempts", 0),
        "max_review_attempts": raw_state.get("max_review_attempts", 3),
        "resume_mode": True,
        "completed_steps": completed,
        "pending_steps": pending,
    }

    pipeline = build_pipeline() if fresh_pipeline else get_pipeline()

    logger.info(
        "pipeline_resumed",
        project_id=state["project_id"],
        completed=completed,
        pending=pending,
        checkpoint=checkpoint_path,
    )

    return pipeline, state


# Pre-compiled singleton
_pipeline_instance: StateGraph | None = None


def get_pipeline() -> StateGraph:
    """Get or create the pipeline singleton."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = build_pipeline()
    return _pipeline_instance
