from __future__ import annotations

from uuid import uuid4

from app.graph.state import create_initial_state, state_summary


class TestGraphState:
    def test_initial_state_creation(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        assert state["idea"] == sample_idea
        assert state["status"] == "pending"
        assert state["current_agent"] is None
        assert state["errors"] == []
        assert state["warnings"] == []
        assert state["revision"] == 0
        assert isinstance(state["project_id"], str)
        assert state["resume_mode"] is False

    def test_state_with_constraints(self, sample_idea: str):
        constraints = {"tech_stack": ["python", "fastapi"]}
        state = create_initial_state(idea=sample_idea, constraints=constraints)
        assert state["constraints"] == constraints

    def test_state_initial_artifacts_are_none(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        for field in ("requirements", "architecture", "source_code", "test_suite", "documentation", "review_report"):
            assert state[field] is None, f"{field} should be None"

    def test_state_pending_steps(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        expected = ["requirements", "architecture", "development", "code_review", "testing", "documentation"]
        assert state["pending_steps"] == expected

    def test_state_review_defaults(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        assert state["review_attempts"] == 0
        assert state["max_review_attempts"] == 3

    def test_state_summary(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        summary = state_summary(state)
        assert summary["status"] == "pending"
        assert summary["revision"] == 0
        assert summary["completed_steps"] == []
        assert len(summary["pending_steps"]) == 6

    def test_state_is_mutable_dict(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["status"] = "running"
        state["revision"] += 1
        assert state["status"] == "running"
        assert state["revision"] == 1

    def test_state_with_custom_project_id(self, sample_idea: str):
        from uuid import uuid4
        pid = uuid4()
        state = create_initial_state(idea=sample_idea, project_id=pid)
        assert state["project_id"] == str(pid)

    def test_state_errors_appended(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["errors"].append({"step": "test", "message": "error1"})
        state["errors"].append({"step": "test", "message": "error2"})
        assert len(state["errors"]) == 2
