from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.agents.prompts.code_review import SYSTEM_PROMPT
from app.core.logging import get_logger
from app.graph.state import GraphState
from app.models.domain.enums import AgentType
from app.models.domain.project import CodeReviewReport, ReviewComment

logger = get_logger(__name__)

VALID_SEVERITIES = {"critical", "warning", "info"}


class CodeReviewAgent(BaseAgent):
    """Reviews generated source code for quality, security, and correctness."""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CODE_REVIEW

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def output_model(self) -> type[CodeReviewReport]:
        return CodeReviewReport

    def build_user_prompt(self, state: GraphState) -> str:
        base = super().build_user_prompt(state)
        source = state.get("source_code", {})
        files_text = ""
        if source:
            file_list = source.get("files", [])
            files_text = "\n\n## Source Code to Review\n"
            for f in file_list:
                path = f.get("path", "unknown")
                content = f.get("content", "")
                lang = f.get("language", "text")
                files_text += f"\n### {path} ({lang})\n```{lang}\n{content}\n```\n"

        return (
            f"{base}\n\n"
            f"## Requirements Context\n"
            f"{state.get('requirements', {}).get('purpose', 'N/A')}\n"
            f"{files_text}\n"
            f"## Instructions\n"
            f"Review every file thoroughly. Check for correctness, security vulnerabilities, "
            f"performance issues, error handling gaps, and adherence to best practices. "
            f"Provide a numeric score and specific, actionable feedback."
        )

    def _validate_output(self, output: CodeReviewReport) -> CodeReviewReport:
        errors: list[str] = []

        if output.overall_score < 0 or output.overall_score > 10:
            errors.append(f"Score must be between 0 and 10, got {output.overall_score}")

        if not output.summary.strip():
            errors.append("Review summary is empty")

        if len(output.strengths) < 3:
            errors.append(f"Too few strengths: {len(output.strengths)} (minimum 3)")
        for i, s in enumerate(output.strengths):
            if not s.strip():
                errors.append(f"Strength at index {i} is empty")

        if len(output.weaknesses) < 3:
            errors.append(f"Too few weaknesses: {len(output.weaknesses)} (minimum 3)")
        for i, w in enumerate(output.weaknesses):
            if not w.strip():
                errors.append(f"Weakness at index {i} is empty")

        for i, c in enumerate(output.comments):
            if not c.file_path.strip():
                errors.append(f"Comment at index {i} has empty file_path")
            if c.line_start < 1:
                errors.append(f"Comment at index {i} has invalid line_start: {c.line_start}")
            if c.line_end < c.line_start:
                errors.append(
                    f"Comment at index {i} has line_end ({c.line_end}) < line_start ({c.line_start})"
                )
            if c.severity not in VALID_SEVERITIES:
                errors.append(
                    f"Comment at index {i} has invalid severity: '{c.severity}' "
                    f"(must be one of: {', '.join(sorted(VALID_SEVERITIES))})"
                )
            if not c.message.strip():
                errors.append(f"Comment at index {i} has empty message")

        if errors:
            error_summary = "\n".join(f"  - {e}" for e in errors)
            logger.warning(
                "code_review_validation_errors",
                error_count=len(errors),
            )
            raise ValueError(
                f"Code review validation failed with {len(errors)} issue(s):\n{error_summary}"
            )

        return output

    def _sanitize_output(self, output: CodeReviewReport) -> CodeReviewReport:
        comments = [
            ReviewComment(
                file_path=c.file_path.strip().replace("\\", "/"),
                line_start=max(c.line_start, 1),
                line_end=max(c.line_end, c.line_start),
                severity=c.severity.strip().lower() if c.severity.strip().lower() in VALID_SEVERITIES else "info",
                message=c.message.strip(),
                suggestion=c.suggestion.strip() if c.suggestion else None,
            )
            for c in output.comments
        ]
        return CodeReviewReport(
            summary=output.summary.strip(),
            overall_score=max(0.0, min(output.overall_score, 10.0)),
            comments=comments,
            strengths=[s.strip() for s in output.strengths if s.strip()],
            weaknesses=[w.strip() for w in output.weaknesses if w.strip()],
            security_concerns=[s.strip() for s in output.security_concerns if s.strip()],
        )

    def _build_state_updates(
        self,
        state: GraphState,
        output: CodeReviewReport,
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
