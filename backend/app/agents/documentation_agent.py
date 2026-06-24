from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.agents.prompts.documentation import SYSTEM_PROMPT
from app.core.logging import get_logger
from app.graph.state import GraphState
from app.models.domain.enums import AgentType
from app.models.domain.project import Documentation

logger = get_logger(__name__)

MIN_README_LENGTH = 100
MIN_SETUP_LENGTH = 50


class DocumentationAgent(BaseAgent):
    """Generates comprehensive technical documentation."""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.DOCUMENTATION

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def output_model(self) -> type[Documentation]:
        return Documentation

    def build_user_prompt(self, state: GraphState) -> str:
        base = super().build_user_prompt(state)

        reqs = state.get("requirements", {})
        arch = state.get("architecture", {})
        source = state.get("source_code", {})
        tests = state.get("test_suite", {})

        source_overview = ""
        if source:
            files = source.get("files", [])
            file_list = "\n".join(
                f"  - {f.get('path', 'unknown')} ({f.get('language', 'text')})"
                for f in files
            )
            source_overview = f"\n### Project Structure\n{file_list}"

        test_overview = ""
        if tests:
            tcs = tests.get("test_cases", [])
            test_overview = (
                f"\n### Test Suite\n"
                f"Framework: {tests.get('test_framework', 'N/A')}\n"
                f"Test Cases: {len(tcs)}\n"
            )

        return (
            f"{base}\n\n"
            f"## Requirements\n"
            f"Title: {reqs.get('title', 'N/A')}\n"
            f"Purpose: {reqs.get('purpose', 'N/A')}\n\n"
            f"## Architecture\n"
            f"Pattern: {arch.get('architecture_pattern', 'N/A')}\n"
            f"Components: {[c.get('name') for c in arch.get('components', [])]}\n\n"
            f"## Source Code\n{source_overview}\n\n"
            f"{test_overview}\n"
            f"## Instructions\n"
            f"Generate complete documentation for this project. "
            f"The README must include setup, usage, and configuration instructions. "
            f"The API documentation must document all endpoints. "
            f"Write for a developer audience — be precise and thorough."
        )

    def _validate_output(self, output: Documentation) -> Documentation:
        errors: list[str] = []

        if not output.readme.strip():
            errors.append("README is empty")
        elif len(output.readme) < MIN_README_LENGTH:
            errors.append(f"README too short: {len(output.readme)} chars (minimum {MIN_README_LENGTH})")

        if not output.setup_guide.strip():
            errors.append("Setup guide is empty")
        elif len(output.setup_guide) < MIN_SETUP_LENGTH:
            errors.append(f"Setup guide too short: {len(output.setup_guide)} chars (minimum {MIN_SETUP_LENGTH})")

        if errors:
            error_summary = "\n".join(f"  - {e}" for e in errors)
            logger.warning(
                "documentation_validation_errors",
                error_count=len(errors),
            )
            raise ValueError(
                f"Documentation validation failed with {len(errors)} issue(s):\n{error_summary}"
            )

        return output

    def _sanitize_output(self, output: Documentation) -> Documentation:
        return Documentation(
            readme=output.readme.strip(),
            setup_guide=output.setup_guide.strip(),
            api_docs=output.api_docs.strip() if output.api_docs else None,
            architecture_overview=output.architecture_overview.strip() if output.architecture_overview else None,
            contributing_guide=output.contributing_guide.strip() if output.contributing_guide else None,
        )

    def _build_state_updates(
        self,
        state: GraphState,
        output: Documentation,
        token_usage: dict[str, int],
    ) -> dict[str, Any]:
        sanitized = self._sanitize_output(output)
        field = self._state_field()
        updates: dict[str, Any] = {
            field: sanitized.model_dump(),
            "current_agent": self.agent_type.value,
            "revision": state["revision"] + 1,
        }
        if token_usage:
            updates["token_usage"] = [
                {"agent": self.agent_type.value, **token_usage}
            ]
        return updates
