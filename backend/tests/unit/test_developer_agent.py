from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.developer_agent import DeveloperAgent
from app.models.domain.enums import AgentType
from app.models.domain.project import ProjectFile, ProjectTree
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
        "requirements": {
            "title": "Todo App",
            "purpose": "Manage tasks",
            "scope": "CLI",
            "functional_requirements": [
                {"id": "FR-01", "description": "Add tasks", "category": "core", "priority": "P0"}
            ],
            "non_functional_requirements": [
                {"id": "NFR-01", "description": "CLI only", "category": "usability"}
            ],
            "user_stories": [
                {"id": "US-01", "description": "As a user, I want to add tasks", "priority": "P0"}
            ],
            "constraints": ["Python only"],
            "assumptions": ["Single user"],
            "open_issues": [],
        },
        "architecture": {
            "title": "Todo App Arch",
            "overview": "A simple CLI app",
            "architecture_pattern": "Layered",
            "components": [
                {"name": "CLI", "description": "Handles CLI args", "technology": "Python",
                 "responsibilities": ["Parse args"], "dependencies": []}
            ],
            "data_flow": [{"step": "1", "source": "CLI", "target": "App"}],
            "tech_stack": {"language": "Python"},
            "deployment_strategy": "Single file deployment",
            "security_considerations": ["Input validation"],
        },
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


@pytest.fixture
def agent():
    llm = MagicMock(spec=LLMService)
    return DeveloperAgent(llm)


class TestDeveloperAgentProperties:
    def test_agent_type(self, agent: DeveloperAgent):
        assert agent.agent_type == AgentType.DEVELOPER

    def test_system_prompt(self, agent: DeveloperAgent):
        assert "Senior Software Engineer" in agent.system_prompt
        assert "Output ONLY valid JSON" in agent.system_prompt
        assert "Good example" in agent.system_prompt
        assert "Bad example" in agent.system_prompt

    def test_output_model(self, agent: DeveloperAgent):
        assert agent.output_model == ProjectTree


class TestValidateOutput:
    def test_rejects_empty_files(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[])
        with pytest.raises(ValueError, match="zero files"):
            agent._validate_output(tree)

    def test_rejects_no_main_entry(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="utils.py", content="x = 1", language="python"),
        ])
        with pytest.raises(ValueError, match="main entry point"):
            agent._validate_output(tree)

    def test_rejects_empty_root(self, agent: DeveloperAgent):
        tree = ProjectTree(root="", files=[
            ProjectFile(path="main.py", content="print('hi')", language="python"),
        ])
        with pytest.raises(ValueError, match="root name is empty"):
            agent._validate_output(tree)

    def test_rejects_absolute_paths(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="/etc/main.py", content="print('hi')", language="python"),
        ])
        with pytest.raises(ValueError, match="invalid path"):
            agent._validate_output(tree)

    def test_rejects_path_traversal(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="../main.py", content="print('hi')", language="python"),
        ])
        with pytest.raises(ValueError, match="invalid path"):
            agent._validate_output(tree)

    def test_rejects_empty_content(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="", language="python"),
        ])
        with pytest.raises(ValueError, match="empty content"):
            agent._validate_output(tree)

    def test_rejects_duplicate_paths(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="print('hi')", language="python"),
            ProjectFile(path="main.py", content="print('bye')", language="python"),
        ])
        with pytest.raises(ValueError, match="Duplicate"):
            agent._validate_output(tree)

    def test_rejects_missing_language(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="print('hi')", language=""),
        ])
        with pytest.raises(ValueError, match="no language"):
            agent._validate_output(tree)

    def test_rejects_missing_required_files(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="print('hi')", language="python"),
        ])
        with pytest.raises(ValueError, match="README.md"):
            agent._validate_output(tree)

    def test_accepts_valid_output(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="print('hello')", language="python"),
            ProjectFile(path="README.md", content="# App", language="markdown"),
            ProjectFile(path="requirements.txt", content="click", language="text"),
        ])
        result = agent._validate_output(tree)
        assert result is tree


class TestSanitizeOutput:
    def test_strips_whitespace(self, agent: DeveloperAgent):
        tree = ProjectTree(root="  App  ", files=[
            ProjectFile(path="  main.py  ", content="  print('hi')  ", language="  PYTHON  "),
        ])
        result = agent._sanitize_output(tree)
        assert result.root == "app"
        assert result.files[0].path == "main.py"
        assert result.files[0].content == "print('hi')"
        assert result.files[0].language == "python"

    def test_deduplicates_files(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="v1", language="python"),
            ProjectFile(path="main.py", content="v2", language="python"),
        ])
        result = agent._sanitize_output(tree)
        assert len(result.files) == 1
        assert result.files[0].content == "v1"

    def test_sorts_files_by_path(self, agent: DeveloperAgent):
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="z.py", content="z", language="python"),
            ProjectFile(path="a.py", content="a", language="python"),
        ])
        result = agent._sanitize_output(tree)
        assert result.files[0].path == "a.py"
        assert result.files[1].path == "z.py"


class TestBuildStateUpdates:
    def test_includes_sanitized_output(self, agent: DeveloperAgent):
        state = _make_state()
        tree = ProjectTree(root="  App  ", files=[
            ProjectFile(path="main.py", content="print('hi')", language="  PYTHON  "),
            ProjectFile(path="README.md", content="# App", language="markdown"),
            ProjectFile(path="requirements.txt", content="click", language="text"),
        ])
        updates = agent._build_state_updates(state, tree, {"prompt_tokens": 10, "completion_tokens": 5})
        source_code = updates["source_code"]
        assert source_code["root"] == "app"
        main_file = next(f for f in source_code["files"] if f["path"] == "main.py")
        assert main_file["language"] == "python"
        assert updates["revision"] == 1

    def test_includes_token_usage(self, agent: DeveloperAgent):
        state = _make_state()
        tree = ProjectTree(root="app", files=[
            ProjectFile(path="main.py", content="print('hi')", language="python"),
            ProjectFile(path="README.md", content="# App", language="markdown"),
            ProjectFile(path="requirements.txt", content="click", language="text"),
        ])
        updates = agent._build_state_updates(state, tree, {"prompt_tokens": 10, "completion_tokens": 5})
        assert len(updates["token_usage"]) == 1
        assert updates["token_usage"][0]["agent"] == "developer"
        assert updates["token_usage"][0]["prompt_tokens"] == 10


class TestBuildUserPrompt:
    def test_includes_requirements_and_architecture(self, agent: DeveloperAgent):
        state = _make_state()
        prompt = agent.build_user_prompt(state)
        assert "Todo App" in prompt
        assert "Layered" in prompt
        assert "CLI" in prompt

    def test_includes_review_feedback_when_present(self, agent: DeveloperAgent):
        state = _make_state(review_report={
            "summary": "Bad code",
            "weaknesses": ["No tests"],
            "security_concerns": [],
            "overall_score": 4.0,
            "comments": [],
            "strengths": [],
            "recommendations": ["Add tests"],
        })
        prompt = agent.build_user_prompt(state)
        assert "Previous Code Review Feedback" in prompt
        assert "Bad code" in prompt
        assert "No tests" in prompt
