from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.agents.code_review_agent import CodeReviewAgent
from app.models.domain.enums import AgentType
from app.models.domain.project import CodeReviewReport, ReviewComment
from app.services.llm_service import LLMService


def _make_state(**overrides) -> dict:
    state: dict = {
        "project_id": str(uuid4()),
        "idea": "Build a CLI todo app",
        "constraints": None,
        "status": "running",
        "current_agent": None,
        "errors": [],
        "warnings": [],
        "requirements": {"title": "App", "purpose": "Manage tasks"},
        "source_code": {
            "root": "todo-app",
            "files": [
                {"path": "src/todo.py", "content": "def add_task(name): return name", "language": "python"},
                {"path": "src/main.py", "content": "def main(): print('hi')", "language": "python"},
            ],
        },
        "architecture": None,
        "test_suite": None,
        "documentation": None,
        "review_report": None,
        "start_time": "2025-01-01T00:00:00",
        "end_time": None,
        "revision": 0,
        "token_usage": [],
        "agent_results": [],
        "review_attempts": 0,
        "max_review_attempts": 3,
        "resume_mode": False,
        "completed_steps": [],
        "pending_steps": [],
    }
    state.update(overrides)
    return state


@pytest.fixture
def agent():
    llm = MagicMock(spec=LLMService)
    return CodeReviewAgent(llm)


def _valid_report(**overrides) -> CodeReviewReport:
    kwargs = dict(
        summary="Good code",
        overall_score=7.0,
        comments=[
            ReviewComment(
                file_path="src/todo.py", line_start=1, line_end=1,
                severity="warning", message="Use type hints", suggestion="Add types",
            ),
        ],
        strengths=["Clean code", "Good structure", "Error handling"],
        weaknesses=["No tests", "Hardcoded values", "Missing logging"],
        security_concerns=["Input not validated"],
    )
    kwargs.update(overrides)
    return CodeReviewReport(**kwargs)


class TestCodeReviewAgentProperties:
    def test_agent_type(self, agent: CodeReviewAgent):
        assert agent.agent_type == AgentType.CODE_REVIEW

    def test_system_prompt(self, agent: CodeReviewAgent):
        assert "Senior Code Reviewer" in agent.system_prompt
        assert "Good example" in agent.system_prompt
        assert "Bad example" in agent.system_prompt

    def test_output_model(self, agent: CodeReviewAgent):
        assert agent.output_model == CodeReviewReport


class TestValidateOutput:
    def test_rejects_score_out_of_range(self, agent: CodeReviewAgent):
        report = CodeReviewReport.model_construct(
            summary="test", overall_score=15.0,
            comments=[], strengths=["A", "B", "C"], weaknesses=["X", "Y", "Z"],
            security_concerns=[],
        )
        with pytest.raises(ValueError, match="Score must be between"):
            agent._validate_output(report)

    def test_rejects_negative_score(self, agent: CodeReviewAgent):
        report = CodeReviewReport.model_construct(
            summary="test", overall_score=-1.0,
            comments=[], strengths=["A", "B", "C"], weaknesses=["X", "Y", "Z"],
            security_concerns=[],
        )
        with pytest.raises(ValueError, match="Score must be between"):
            agent._validate_output(report)

    def test_rejects_empty_summary(self, agent: CodeReviewAgent):
        report = _valid_report(summary="")
        with pytest.raises(ValueError, match="summary is empty"):
            agent._validate_output(report)

    def test_rejects_too_few_strengths(self, agent: CodeReviewAgent):
        report = _valid_report(strengths=["Only one"])
        with pytest.raises(ValueError, match="Too few strengths"):
            agent._validate_output(report)

    def test_rejects_too_few_weaknesses(self, agent: CodeReviewAgent):
        report = _valid_report(weaknesses=["Only one"])
        with pytest.raises(ValueError, match="Too few weaknesses"):
            agent._validate_output(report)

    def test_rejects_empty_strength_item(self, agent: CodeReviewAgent):
        report = _valid_report(strengths=["", "Good structure", "Error handling"])
        with pytest.raises(ValueError, match="Strength at index 0"):
            agent._validate_output(report)

    def test_rejects_empty_comment_file_path(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="", line_start=1, line_end=1, severity="info", message="msg",
        )])
        with pytest.raises(ValueError, match="empty file_path"):
            agent._validate_output(report)

    def test_rejects_invalid_line_start(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=0, line_end=1, severity="info", message="msg",
        )])
        with pytest.raises(ValueError, match="invalid line_start"):
            agent._validate_output(report)

    def test_rejects_line_end_before_start(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=10, line_end=5, severity="info", message="msg",
        )])
        with pytest.raises(ValueError, match="line_end"):
            agent._validate_output(report)

    def test_rejects_invalid_severity(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=1, line_end=1, severity="blocker", message="msg",
        )])
        with pytest.raises(ValueError, match="invalid severity"):
            agent._validate_output(report)

    def test_rejects_empty_comment_message(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=1, line_end=1, severity="info", message="",
        )])
        with pytest.raises(ValueError, match="empty message"):
            agent._validate_output(report)

    def test_accepts_valid_report(self, agent: CodeReviewAgent):
        report = _valid_report()
        result = agent._validate_output(report)
        assert result is report


class TestSanitizeOutput:
    def test_clamps_score(self, agent: CodeReviewAgent):
        report = CodeReviewReport.model_construct(
            summary="test", overall_score=99.9,
            comments=[], strengths=["A", "B", "C"], weaknesses=["X", "Y", "Z"],
            security_concerns=[],
        )
        result = agent._sanitize_output(report)
        assert result.overall_score == 10.0

        report2 = CodeReviewReport.model_construct(
            summary="test", overall_score=-5.0,
            comments=[], strengths=["A", "B", "C"], weaknesses=["X", "Y", "Z"],
            security_concerns=[],
        )
        result2 = agent._sanitize_output(report2)
        assert result2.overall_score == 0.0

    def test_normalizes_severity(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=1, line_end=1,
            severity="  CRITICAL  ", message="msg",
        )])
        result = agent._sanitize_output(report)
        assert result.comments[0].severity == "critical"

    def test_fixes_line_end(self, agent: CodeReviewAgent):
        report = _valid_report(comments=[ReviewComment(
            file_path="src/todo.py", line_start=5, line_end=3, severity="info", message="msg",
        )])
        result = agent._sanitize_output(report)
        assert result.comments[0].line_end >= result.comments[0].line_start

    def test_strips_empty_items(self, agent: CodeReviewAgent):
        report = _valid_report(
            strengths=["A", "", "B", "C"],
            weaknesses=["X", "Y", "", "Z"],
            security_concerns=["", "S1", ""],
        )
        result = agent._sanitize_output(report)
        assert all(s for s in result.strengths)
        assert all(w for w in result.weaknesses)
        assert all(s for s in result.security_concerns)


class TestBuildStateUpdates:
    def test_includes_sanitized_output(self, agent: CodeReviewAgent):
        state = _make_state()
        report = CodeReviewReport(
            summary="  Good  ", overall_score=7.0,
            comments=[ReviewComment(
                file_path="src/todo.py", line_start=1, line_end=1,
                severity="  WARNING  ", message="  msg  ",
            )],
            strengths=["A", "B", "C"], weaknesses=["X", "Y", "Z"],
            security_concerns=["S1"],
        )
        updates = agent._build_state_updates(state, report, {"prompt_tokens": 5, "completion_tokens": 3})
        review = updates["review_report"]
        assert review["summary"] == "Good"
        assert review["comments"][0]["severity"] == "warning"
        assert updates["revision"] == 1

    def test_includes_token_usage(self, agent: CodeReviewAgent):
        state = _make_state()
        report = _valid_report()
        updates = agent._build_state_updates(state, report, {"prompt_tokens": 5, "completion_tokens": 3})
        assert len(updates["token_usage"]) == 1
        assert updates["token_usage"][0]["agent"] == "code_review"


class TestBuildUserPrompt:
    def test_includes_source_code(self, agent: CodeReviewAgent):
        state = _make_state()
        prompt = agent.build_user_prompt(state)
        assert "src/todo.py" in prompt
        assert "src/main.py" in prompt
