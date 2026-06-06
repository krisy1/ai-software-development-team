from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.worker.tasks import run_generation_pipeline


def _make_request_id():
    """Set up a mock Celery request context via ``push_request``.

    Returns the previously pushed request (for cleanup).
    """
    run_generation_pipeline.push_request(id="mock-task-id")


def _pop_request():
    run_generation_pipeline.pop_request()


def _mock_retry():
    """Patch ``self.retry`` so that it raises an exception immediately."""
    patcher = patch.object(
        run_generation_pipeline,
        "retry",
        side_effect=Exception("retry-called"),
    )
    patcher.start()
    return patcher


def _dummy_state(**overrides: str) -> dict:
    """Build a minimal valid ``GraphState`` dict matching ``state_summary`` expectations."""
    state: dict = {
        "project_id": str(uuid4()),
        "idea": "Build a task manager",
        "constraints": None,
        "status": "running",
        "current_agent": None,
        "errors": [],
        "warnings": [],
        "requirements": None,
        "architecture": None,
        "source_code": None,
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


def _final_state(**overrides) -> dict:
    """Build a minimal ``pipeline.ainvoke()`` return value that passes ``state_summary``."""
    state = _dummy_state()
    state.update(overrides)
    return state


class TestAsyncInvocation:
    """Verify the Celery task uses async ``ainvoke()`` with the correct config."""

    def setup_method(self):
        _make_request_id()

    def teardown_method(self):
        _pop_request()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_uses_ainvoke_instead_of_invoke(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(
            return_value=_final_state(status="completed", revision=1)
        )
        mock_get_pipeline.return_value = mock_pipeline

        run_generation_pipeline.run(
            idea="test idea", project_id=str(uuid4())
        )

        mock_pipeline.ainvoke.assert_called_once()
        mock_pipeline.invoke.assert_not_called()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_ainvoke_receives_thread_id_config(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        project_id = str(uuid4())
        mock_create_state.return_value = _dummy_state(project_id=project_id)
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(
            return_value=_final_state(status="completed", revision=1)
        )
        mock_get_pipeline.return_value = mock_pipeline

        run_generation_pipeline.run(
            idea="test idea", project_id=project_id
        )

        mock_pipeline.ainvoke.assert_called_once()
        _call_kwargs = mock_pipeline.ainvoke.call_args.kwargs
        config = _call_kwargs.get("config", {})
        assert config.get("configurable", {}).get("thread_id") == project_id

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_pipeline_state_passed_as_first_arg(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        dummy_state = _dummy_state()
        mock_create_state.return_value = dummy_state
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(
            return_value=_final_state(status="completed", revision=1)
        )
        mock_get_pipeline.return_value = mock_pipeline

        project_id = dummy_state["project_id"]
        run_generation_pipeline.run(
            idea="test idea", project_id=project_id
        )

        mock_pipeline.ainvoke.assert_called_once_with(
            dummy_state,
            config={"configurable": {"thread_id": project_id}},
        )


class TestTaskResultFormat:
    """Verify the task return value matches the expected contract."""

    def setup_method(self):
        _make_request_id()

    def teardown_method(self):
        _pop_request()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_returns_correct_structure(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        project_id = str(uuid4())
        final_state = _final_state(
            project_id=project_id,
            status="completed",
            revision=3,
            requirements={"title": "Req"},
            architecture={"pattern": "microservices", "overview": "Overview"},
            source_code={"files": []},
            test_suite={"test_framework": "pytest", "test_cases": []},
            documentation={"readme": "# Project", "setup_guide": "pip install"},
            review_report={
                "summary": "Good",
                "overall_score": 8.5,
                "comments": [],
                "strengths": [],
                "weaknesses": [],
                "security_concerns": [],
            },
            errors=[{"step": "test", "message": "warning"}],
            warnings=[{"step": "test", "message": "note"}],
        )

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(return_value=final_state)
        mock_get_pipeline.return_value = mock_pipeline

        result = run_generation_pipeline.run(
            idea="test", project_id=project_id
        )

        assert result["project_id"] == project_id
        assert result["status"] == "completed"
        assert result["revision"] == 3
        assert result["has_requirements"] is True
        assert result["has_architecture"] is True
        assert result["has_source_code"] is True
        assert result["has_tests"] is True
        assert result["has_documentation"] is True
        assert result["has_review"] is True
        assert result["error_count"] == 1
        assert result["warning_count"] == 1

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_handles_null_artifacts(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        final_state = _final_state(
            status="running", revision=1,
            requirements=None, architecture=None,
            source_code=None, test_suite=None,
            documentation=None, review_report=None,
            errors=[], warnings=[],
        )

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(return_value=final_state)
        mock_get_pipeline.return_value = mock_pipeline

        result = run_generation_pipeline.run(
            idea="test", project_id=str(uuid4())
        )

        assert result["status"] == "running"
        assert result["has_requirements"] is False
        assert result["has_architecture"] is False
        assert result["has_source_code"] is False
        assert result["has_tests"] is False
        assert result["has_documentation"] is False
        assert result["has_review"] is False
        assert result["error_count"] == 0

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_includes_all_expected_return_keys(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(
            return_value=_final_state(status="completed", revision=1)
        )
        mock_get_pipeline.return_value = mock_pipeline

        result = run_generation_pipeline.run(
            idea="test", project_id=str(uuid4())
        )

        expected_keys = {
            "project_id", "status", "revision",
            "has_requirements", "has_architecture", "has_source_code",
            "has_tests", "has_documentation", "has_review",
            "error_count", "warning_count",
        }
        assert set(result.keys()) == expected_keys


class TestTaskErrorHandling:
    """Verify error propagation and retry behaviour."""

    def setup_method(self):
        _make_request_id()

    def teardown_method(self):
        _pop_request()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_pipeline_exception_triggers_retry(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(side_effect=RuntimeError("pipeline crash"))
        mock_get_pipeline.return_value = mock_pipeline

        retry_patcher = _mock_retry()

        with pytest.raises(Exception, match="retry-called"):
            run_generation_pipeline.run(
                idea="test", project_id=str(uuid4())
            )

        retry_patcher.stop()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_create_initial_state_exception_triggers_retry(
        self,
        mock_create_state,
        _mock_get_pipeline,  # not used (create_initial_state raises before get_pipeline)
        mock_llm,
    ):
        mock_create_state.side_effect = ValueError("invalid idea")
        mock_llm.is_available = False

        retry_patcher = _mock_retry()

        with pytest.raises(Exception, match="retry-called"):
            run_generation_pipeline.run(
                idea="", project_id=str(uuid4())
            )

        retry_patcher.stop()


class TestAsyncBridgeSafety:
    """Verify the sync-to-async bridge in ``worker/tasks.py``."""

    def setup_method(self):
        _make_request_id()

    def teardown_method(self):
        _pop_request()

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_can_instantiate_and_invoke_pipeline_directly(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        result_value = _final_state(status="completed", revision=2)
        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(return_value=result_value)
        mock_get_pipeline.return_value = mock_pipeline

        result = run_generation_pipeline.run(
            idea="test", project_id=str(uuid4())
        )

        assert result["status"] == "completed"
        assert result["revision"] == 2

    @patch("app.worker.tasks.llm_service")
    @patch("app.worker.tasks.get_pipeline")
    @patch("app.worker.tasks.create_initial_state")
    def test_avoids_event_loop_leak(
        self,
        mock_create_state,
        mock_get_pipeline,
        mock_llm,
    ):
        mock_create_state.return_value = _dummy_state()
        mock_llm.is_available = False

        mock_pipeline = MagicMock()
        mock_pipeline.ainvoke = AsyncMock(
            return_value=_final_state(status="completed", revision=1)
        )
        mock_get_pipeline.return_value = mock_pipeline

        for _ in range(5):
            result = run_generation_pipeline.run(
                idea="test", project_id=str(uuid4())
            )
            assert result["status"] == "completed"
