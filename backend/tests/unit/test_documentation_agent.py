from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.agents.documentation_agent import DocumentationAgent
from app.models.domain.enums import AgentType
from app.models.domain.project import Documentation
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
        "requirements": {"title": "Todo App", "purpose": "Manage tasks"},
        "architecture": {
            "architecture_pattern": "Layered",
            "components": [{"name": "CLI", "description": "CLI handler"}],
        },
        "source_code": {
            "root": "todo-app",
            "files": [
                {"path": "src/todo.py", "content": "def add_task(name): return name", "language": "python"},
            ],
        },
        "test_suite": {
            "test_framework": "pytest",
            "test_cases": [{"name": "test_add", "description": "Test add", "type": "unit"}],
        },
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
    return DocumentationAgent(llm)


def _valid_doc(**overrides) -> Documentation:
    kwargs = dict(
        readme="# Project\n\nA CLI todo app.\n\n## Setup\npip install -r requirements.txt\n\n" + "x" * 100,
        setup_guide="## Prerequisites\nPython 3.10+\n\n## Install\npip install -r requirements.txt\n" + "x" * 50,
        api_docs="## API\n\n### POST /tasks\nCreates a task.\n",
        architecture_overview="## Architecture\nLayered architecture with CLI layer.\n",
        contributing_guide="## Contributing\nFork and PR.\n",
    )
    kwargs.update(overrides)
    return Documentation(**kwargs)


class TestDocumentationAgentProperties:
    def test_agent_type(self, agent: DocumentationAgent):
        assert agent.agent_type == AgentType.DOCUMENTATION

    def test_system_prompt(self, agent: DocumentationAgent):
        assert "Technical Writer" in agent.system_prompt
        assert "Good example" in agent.system_prompt
        assert "Bad example" in agent.system_prompt

    def test_output_model(self, agent: DocumentationAgent):
        assert agent.output_model == Documentation


class TestValidateOutput:
    def test_rejects_empty_readme(self, agent: DocumentationAgent):
        doc = _valid_doc(readme="")
        with pytest.raises(ValueError, match="README is empty"):
            agent._validate_output(doc)

    def test_rejects_short_readme(self, agent: DocumentationAgent):
        doc = _valid_doc(readme="# Short")
        with pytest.raises(ValueError, match="README too short"):
            agent._validate_output(doc)

    def test_rejects_empty_setup_guide(self, agent: DocumentationAgent):
        doc = _valid_doc(setup_guide="")
        with pytest.raises(ValueError, match="Setup guide is empty"):
            agent._validate_output(doc)

    def test_rejects_short_setup_guide(self, agent: DocumentationAgent):
        doc = _valid_doc(setup_guide="Short")
        with pytest.raises(ValueError, match="Setup guide too short"):
            agent._validate_output(doc)

    def test_accepts_valid_documentation(self, agent: DocumentationAgent):
        doc = _valid_doc()
        result = agent._validate_output(doc)
        assert result is doc


class TestSanitizeOutput:
    def test_strips_whitespace(self, agent: DocumentationAgent):
        doc = Documentation(
            readme="  # Project  ", setup_guide="  ## Setup  ",
            api_docs="  API docs  ", architecture_overview="  Arch  ",
            contributing_guide="  Contrib  ",
        )
        result = agent._sanitize_output(doc)
        assert result.readme == "# Project"
        assert result.setup_guide == "## Setup"
        assert result.api_docs == "API docs"


class TestBuildStateUpdates:
    def test_includes_sanitized_output(self, agent: DocumentationAgent):
        state = _make_state()
        doc = Documentation(
            readme="  # Project  ", setup_guide="  ## Setup  ",
            api_docs="  API docs  ",
        )
        updates = agent._build_state_updates(state, doc, {"prompt_tokens": 5, "completion_tokens": 3})
        documentation = updates["documentation"]
        assert documentation["readme"] == "# Project"
        assert updates["revision"] == 1

    def test_includes_token_usage(self, agent: DocumentationAgent):
        state = _make_state()
        doc = _valid_doc()
        updates = agent._build_state_updates(state, doc, {"prompt_tokens": 5, "completion_tokens": 3})
        assert len(updates["token_usage"]) == 1
        assert updates["token_usage"][0]["agent"] == "documentation"


class TestBuildUserPrompt:
    def test_includes_context(self, agent: DocumentationAgent):
        state = _make_state()
        prompt = agent.build_user_prompt(state)
        assert "Layered" in prompt
        assert "src/todo.py" in prompt
        assert "pytest" in prompt
