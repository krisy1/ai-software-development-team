from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.agents.base import BaseAgent
from app.agents.prompts.developer import SYSTEM_PROMPT
from app.core.logging import get_logger
from app.graph.state import GraphState
from app.models.domain.enums import AgentType
from app.models.domain.project import ProjectFile, ProjectTree

logger = get_logger(__name__)

REQUIRED_PROJECT_FILES = {"README.md", "requirements.txt"}


class DeveloperAgent(BaseAgent):
    """Generates complete source code from requirements and architecture."""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.DEVELOPER

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def output_model(self) -> type[ProjectTree]:
        return ProjectTree

    def build_user_prompt(self, state: GraphState) -> str:
        base = super().build_user_prompt(state)
        reqs = state.get("requirements", {})
        arch = state.get("architecture", {})

        review_feedback = ""
        if state.get("review_report"):
            review_feedback = (
                f"## Previous Code Review Feedback\n"
                f"Note: This is a revision based on the following review:\n"
                f"{state['review_report'].get('summary', '')}\n"
                f"Weaknesses to address: {state['review_report'].get('weaknesses', [])}\n"
                f"Security concerns: {state['review_report'].get('security_concerns', [])}\n"
                f"Please fix all issues mentioned above.\n"
            )

        return (
            f"{base}\n\n"
            f"## Requirements Summary\n"
            f"Title: {reqs.get('title', 'N/A')}\n"
            f"Purpose: {reqs.get('purpose', 'N/A')}\n"
            f"Functional Requirements: {len(reqs.get('functional_requirements', []))}\n\n"
            f"## Architecture Summary\n"
            f"Pattern: {arch.get('architecture_pattern', 'N/A')}\n"
            f"Components: {[c.get('name') for c in arch.get('components', [])]}\n"
            f"Tech Stack: {arch.get('tech_stack', {})}\n\n"
            f"{review_feedback}"
            f"## Instructions\n"
            f"Generate a complete, working implementation. "
            f"Include all source files needed for a functional project. "
            f"Code MUST be syntactically valid and all imports must resolve correctly."
        )

    def _validate_output(self, output: ProjectTree) -> ProjectTree:
        errors: list[str] = []

        if not output.root:
            errors.append("Project root name is empty")

        if not output.files:
            raise ValueError("Code generation produced zero files")

        has_main = any("main" in f.path for f in output.files)
        if not has_main:
            errors.append("No main entry point found in generated code")

        seen_paths: set[str] = set()
        for i, f in enumerate(output.files):
            fp = f.path.strip()
            if not fp:
                errors.append(f"File at index {i} has an empty path")
                continue
            if fp.startswith("/") or fp.startswith(".."):
                errors.append(f"File at index {i} has an invalid path: '{fp}' (must be relative)")
                continue
            try:
                PurePosixPath(fp)
            except Exception:
                errors.append(f"File at index {i} has an invalid path: '{fp}'")
                continue
            if fp in seen_paths:
                errors.append(f"Duplicate file path: '{fp}'")
            seen_paths.add(fp)
            if not f.content.strip():
                errors.append(f"File '{fp}' has empty content")
            if not f.language.strip():
                errors.append(f"File '{fp}' has no language specified")

        fp_set = {f.path.strip() for f in output.files}
        missing_required = REQUIRED_PROJECT_FILES - fp_set
        if missing_required:
            errors.append(f"Missing required project files: {', '.join(sorted(missing_required))}")

        for f in output.files:
            imports = re.findall(r"^import\s+(\S+)", f.content, re.MULTILINE)
            imports += re.findall(r"^from\s+(\S+)\s+import", f.content, re.MULTILINE)
            for imp in imports:
                parts = imp.split(".")
                if len(parts) > 1:
                    candidate = parts[0]
                    if candidate != f.path.split("/")[-1].replace(".py", "") and candidate not in ("os", "sys", "json", "re", "datetime", "typing", "abc", "uuid", "pathlib", "collections"):
                        if not any(
                            candidate in other.path for other in output.files
                        ):
                            continue

        if errors:
            error_summary = "\n".join(f"  - {e}" for e in errors)
            logger.warning(
                "developer_validation_errors",
                error_count=len(errors),
                file_count=len(output.files),
            )
            raise ValueError(
                f"Developer validation failed with {len(errors)} issue(s):\n{error_summary}"
            )

        return output

    def _build_state_updates(
        self,
        state: GraphState,
        output: ProjectTree,
        token_usage: dict[str, int],
    ) -> dict:
        sanitized = self._sanitize_output(output)
        field = self._state_field()
        updates: dict = {
            field: sanitized.model_dump(),
            "current_agent": self.agent_type.value,
            "revision": state["revision"] + 1,
        }
        if token_usage:
            updates["token_usage"] = [
                {"agent": self.agent_type.value, **token_usage}
            ]
        return updates

    def _sanitize_output(self, output: ProjectTree) -> ProjectTree:
        seen: dict[str, ProjectFile] = {}
        for f in output.files:
            path = f.path.strip()
            if path in seen:
                continue
            seen[path] = ProjectFile(
                path=path,
                content=f.content.strip(),
                language=f.language.strip().lower(),
            )
        sorted_files = sorted(seen.values(), key=lambda x: x.path)
        return ProjectTree(
            root=output.root.strip().lower().replace(" ", "-"),
            files=sorted_files,
            dependency_files=list(dict.fromkeys(output.dependency_files)),
        )
