from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.graph.nodes import _should_skip
from app.graph.pipeline import _clean_pending_steps, resume_from_checkpoint
from app.graph.state import create_initial_state
from app.services.storage_service import LOGS_DIR, StorageService, storage_service


@pytest.fixture(autouse=True)
def clean_storage():
    """Clean storage dirs before and after resume tests."""
    for d in (LOGS_DIR,):
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()
    yield
    for d in (LOGS_DIR,):
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()


class TestShouldSkip:
    def test_skips_when_resume_mode_and_step_completed(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["resume_mode"] = True
        state["completed_steps"] = ["requirements"]
        state["requirements"] = {"title": "Existing"}
        assert _should_skip(state, "requirements") is True

    def test_does_not_skip_when_resume_mode_but_step_incomplete(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["resume_mode"] = True
        state["completed_steps"] = ["requirements"]
        # architecture not in completed_steps
        assert _should_skip(state, "architect") is False

    def test_does_not_skip_when_not_resume_mode(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["resume_mode"] = False
        state["completed_steps"] = ["requirements"]
        state["requirements"] = {"title": "Existing"}
        assert _should_skip(state, "requirements") is False

    def test_does_not_skip_for_unknown_agent(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["resume_mode"] = True
        assert _should_skip(state, "unknown_agent") is False

    def test_does_not_skip_when_artifact_is_none(self, sample_idea: str):
        state = create_initial_state(idea=sample_idea)
        state["resume_mode"] = True
        state["completed_steps"] = ["requirements"]
        state["requirements"] = None  # artifact missing
        assert _should_skip(state, "requirements") is False


class TestCleanPendingSteps:
    def test_all_steps_pending_initially(self):
        pending = _clean_pending_steps([])
        assert pending == ["requirements", "architecture", "development", "code_review", "testing", "documentation"]

    def test_removes_completed_steps(self):
        pending = _clean_pending_steps(["requirements", "architecture"])
        assert pending == ["development", "code_review", "testing", "documentation"]

    def test_returns_empty_when_all_done(self):
        pending = _clean_pending_steps(["requirements", "architecture", "development", "code_review", "testing", "documentation"])
        assert pending == []

    def test_ignores_unknown_steps(self):
        pending = _clean_pending_steps(["requirements", "foobar"])
        assert pending == ["architecture", "development", "code_review", "testing", "documentation"]


class TestResumeFromCheckpoint:
    def test_raises_on_missing_checkpoint(self):
        with pytest.raises(FileNotFoundError):
            resume_from_checkpoint("/nonexistent/checkpoint.json")

    def test_reconstructs_state_from_checkpoint(self, sample_idea: str):
        pid = str(uuid4())
        storage_service.save_checkpoint(
            project_id=pid,
            state={
                "idea": sample_idea,
                "project_id": pid,
                "status": "running",
                "requirements": {"title": "Existing Reqs", "purpose": "Test purpose here"},
                "architecture": None,
                "source_code": None,
                "test_suite": None,
                "documentation": None,
                "review_report": None,
                "completed_steps": ["requirements"],
                "pending_steps": ["architecture", "development", "code_review", "testing", "documentation"],
                "revision": 2,
                "review_attempts": 0,
                "max_review_attempts": 3,
                "errors": [],
                "warnings": [],
                "token_usage": [{"agent": "requirements", "total_tokens": 150}],
                "agent_results": [],
                "start_time": "2026-01-01T00:00:00",
                "end_time": None,
                "constraints": None,
                "current_agent": "requirements",
                "resume_mode": False,
            },
            description="Test checkpoint",
        )
        cps = storage_service.list_checkpoints(project_id=pid)
        assert len(cps) == 1

        pipeline, state = resume_from_checkpoint(str(cps[0]))
        assert state["project_id"] == pid
        assert state["resume_mode"] is True
        assert state["status"] == "running"
        assert state["requirements"] == {"title": "Existing Reqs", "purpose": "Test purpose here"}
        assert state["architecture"] is None
        assert state["completed_steps"] == ["requirements"]
        assert "requirements" not in state["pending_steps"]
        assert "architecture" in state["pending_steps"]

    def test_resume_fast_forwards_past_completed_node(self, sample_idea: str):
        pid = str(uuid4())
        storage_service.save_checkpoint(
            project_id=pid,
            state={
                "idea": sample_idea,
                "project_id": pid,
                "status": "running",
                "requirements": {"title": "Done", "purpose": "Test purpose here"},
                "architecture": {"components": [], "overview": "Done arch overview here"},
                "source_code": None,
                "test_suite": None,
                "documentation": None,
                "review_report": None,
                "completed_steps": ["requirements", "architecture"],
                "pending_steps": ["development", "code_review", "testing", "documentation"],
                "revision": 3,
                "review_attempts": 0,
                "max_review_attempts": 3,
                "errors": [],
                "warnings": [],
                "token_usage": [],
                "agent_results": [],
                "start_time": "2026-01-01T00:00:00",
                "end_time": None,
                "constraints": None,
                "current_agent": "architect",
                "resume_mode": False,
            },
            description="Mid-pipeline checkpoint",
        )
        cps = storage_service.list_checkpoints(project_id=pid)
        pipeline, state = resume_from_checkpoint(str(cps[0]))

        assert state["requirements"] is not None
        assert state["architecture"] is not None
        assert state["source_code"] is None
        assert state["completed_steps"] == ["requirements", "architecture"]
        assert state["pending_steps"] == ["development", "code_review", "testing", "documentation"]

    def test_resume_preserves_errors_and_warnings(self, sample_idea: str):
        pid = str(uuid4())
        storage_service.save_checkpoint(
            project_id=pid,
            state={
                "idea": sample_idea,
                "project_id": pid,
                "status": "running",
                "requirements": None,
                "architecture": None,
                "source_code": None,
                "test_suite": None,
                "documentation": None,
                "review_report": None,
                "completed_steps": [],
                "pending_steps": ["requirements", "architecture", "development", "code_review", "testing", "documentation"],
                "revision": 0,
                "review_attempts": 0,
                "max_review_attempts": 3,
                "errors": [{"step": "validate", "message": "previous error"}],
                "warnings": [{"step": "validate", "message": "previous warning"}],
                "token_usage": [],
                "agent_results": [],
                "start_time": "2026-01-01T00:00:00",
                "end_time": None,
                "constraints": None,
                "current_agent": None,
                "resume_mode": False,
            },
            description="With errors",
        )
        cps = storage_service.list_checkpoints(project_id=pid)
        _, state = resume_from_checkpoint(str(cps[0]))
        assert len(state["errors"]) == 1
        assert state["errors"][0]["message"] == "previous error"
        assert len(state["warnings"]) == 1


class TestExecutionLogs:
    def test_save_and_load_logs(self):
        pid = str(uuid4())
        log1 = {"timestamp": "2026-01-01T00:00:00", "agent": "requirements", "status": "running"}
        log2 = {"timestamp": "2026-01-01T00:01:00", "agent": "architect", "status": "running"}
        log3 = {"timestamp": "2026-01-01T00:02:00", "agent": "persistence", "status": "completed"}

        s = StorageService()
        s.save_execution_log(pid, log1)
        s.save_execution_log(pid, log2)
        s.save_execution_log(pid, log3)

        entries = s.load_execution_logs(pid)
        assert len(entries) == 3
        assert entries[0]["agent"] == "requirements"
        assert entries[1]["agent"] == "architect"
        assert entries[2]["agent"] == "persistence"

    def test_load_logs_returns_empty_for_missing_project(self):
        s = StorageService()
        entries = s.load_execution_logs("nonexistent-project")
        assert entries == []

    def test_logs_are_ndjson(self):
        pid = str(uuid4())
        s = StorageService()
        s.save_execution_log(pid, {"agent": "test"})

        log_path = LOGS_DIR / f"{pid}.ndjson"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["agent"] == "test"
