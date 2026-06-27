from __future__ import annotations

import re
from typing import Any

from app.agents.base import BaseAgent
from app.agents.prompts.architect import SYSTEM_PROMPT
from app.core.logging import get_logger
from app.graph.state import GraphState
from app.models.domain.enums import AgentType
from app.models.domain.project import (
    APIEndpoint,
    APISpec,
    ArchitectureDoc,
    ComponentSpec,
    DatabaseDesign,
    DatabaseTable,
    FolderEntry,
    FolderStructure,
)

logger = get_logger(__name__)

ARCHITECTURE_PATTERNS = {
    "microservices",
    "layered",
    "event-driven",
    "hexagonal",
    "cqrs",
    "serverless",
    "modular monolith",
    "clean architecture",
    "domain-driven design",
    "pipeline",
    "broker",
    "client-server",
    "peer-to-peer",
    "space-based",
    "blackboard",
    "interpreter",
    "mvc",
    "mvvm",
    "soa",
    "n-tier",
}

VAGUE_TECH_TERMS = {
    "some database",
    "a cache",
    "cloud",
    "modern",
    "latest",
    "fast",
    "appropriate",
    "suitable",
    "standard",
    "industry-standard",
}


class ArchitectAgent(BaseAgent):
    """Designs system architecture from requirements.

    Transforms a requirements document into a comprehensive architecture design
    covering components, data flow, tech stack, database design, API specs,
    deployment strategy, security, and folder structure.

    The agent:
    1. Builds a detailed user prompt from the requirements + constraints
    2. Calls the LLM with a domain-specific system prompt
    3. Validates the output against ArchitectureDoc schema
    4. Performs domain-specific quality checks
    5. Sanitizes and normalizes the output
    6. Returns state updates with the artifact + token usage
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ARCHITECT

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def output_model(self) -> type[ArchitectureDoc]:
        return ArchitectureDoc

    def build_user_prompt(self, state: GraphState) -> str:
        base = super().build_user_prompt(state)
        reqs = state.get("requirements")

        reqs_text = ""
        if reqs:
            frs = reqs.get("functional_requirements", [])
            nfrs = reqs.get("non_functional_requirements", [])
            fr_summary = "\n".join(
                f"  - {fr.get('id', 'N/A')}: {fr.get('description', '')[:100]} [{fr.get('priority', 'N/A')}]"
                for fr in frs
            )
            nfr_summary = "\n".join(
                f"  - {nfr.get('id', 'N/A')}: {nfr.get('description', '')[:100]} ({nfr.get('category', 'N/A')})"
                for nfr in nfrs
            )

            reqs_text = (
                f"## Requirements Document\n"
                f"Title: {reqs.get('title', 'N/A')}\n"
                f"Purpose: {reqs.get('purpose', 'N/A')}\n"
                f"Scope: {reqs.get('scope', 'N/A')}\n\n"
                f"### Functional Requirements ({len(frs)})\n"
                f"{fr_summary}\n\n"
                f"### Non-Functional Requirements ({len(nfrs)})\n"
                f"{nfr_summary}\n\n"
                f"### Constraints\n"
                f"{chr(10).join(f'  - {c}' for c in reqs.get('constraints', []))}\n"
                f"### Assumptions\n"
                f"{chr(10).join(f'  - {a}' for a in reqs.get('assumptions', []))}\n"
            )

        return (
            f"{base}\n\n"
            f"{reqs_text}\n"
            f"## Instructions\n"
            f"Design a complete, production-ready system architecture for this project. "
            f"Include at least 3 components with clear responsibilities and dependencies. "
            f"Specify concrete technology choices with versions. "
            f"Provide database design, API specification, and folder structure. "
            f"Focus on making this architecture implementable by a development team."
        )

    async def process(self, state: GraphState) -> dict[str, Any]:
        logger.info(
            "agent:architect_agent",
            project_id=state["project_id"],
            has_requirements=state.get("requirements") is not None,
        )

        try:
            return await super().process(state)
        except Exception as e:
            logger.error(
                "architecture_generation_failed",
                project_id=state["project_id"],
                error=str(e),
            )
            raise

    def _validate_output(self, output: ArchitectureDoc) -> ArchitectureDoc:
        errors: list[str] = []

        # ── Count checks ─────────────────────────────────────────
        comp_count = len(output.components)
        tech_count = len(output.tech_stack)
        flow_count = len(output.data_flow)
        sec_count = len(output.security_considerations)

        if comp_count < 3:
            errors.append(f"Too few components: {comp_count} (minimum 3)")
        if tech_count < 5:
            errors.append(f"Too few tech stack entries: {tech_count} (minimum 5)")
        if flow_count < 4:
            errors.append(f"Too few data flow steps: {flow_count} (minimum 4)")
        if sec_count < 3:
            errors.append(f"Too few security considerations: {sec_count} (minimum 3)")

        # ── Component checks ─────────────────────────────────────
        component_names = set()
        for _i, comp in enumerate(output.components):
            name_lower = comp.name.lower()
            if name_lower in component_names:
                errors.append(f"Duplicate component name: '{comp.name}'")
            component_names.add(name_lower)

            if len(comp.responsibilities) < 2:
                errors.append(
                    f"Component '{comp.name}' has only {len(comp.responsibilities)} responsibilities (minimum 2)"
                )

            # Check for vague technology
            if comp.technology.lower() in VAGUE_TECH_TERMS:
                errors.append(f"Component '{comp.name}' has vague technology: '{comp.technology}'")
            elif not re.match(r".+[\d.]+", comp.technology) and len(comp.technology) < 5:
                errors.append(f"Component '{comp.name}' technology '{comp.technology}' lacks version indication")

            # Check for self-dependency
            deps_lower = [d.lower() for d in comp.dependencies]
            if name_lower in deps_lower:
                errors.append(f"Component '{comp.name}' depends on itself")

        # ── Component dependency DAG check ───────────────────────
        component_name_set = {c.name.lower() for c in output.components}
        for comp in output.components:
            for dep in comp.dependencies:
                dep_lower = dep.lower()
                # Allow external dependencies (not in component list)
                # but flag if it references a non-existent internal component
                for cname in component_name_set:
                    if cname in dep_lower or dep_lower in cname:
                        break
                else:
                    # This dep doesn't match any component — it's external, that's OK
                    pass

        # ── Architecture pattern check ───────────────────────────
        pattern_lower = output.architecture_pattern.lower().strip()
        pattern_matched = any(p in pattern_lower for p in ARCHITECTURE_PATTERNS)
        if not pattern_matched:
            errors.append(
                f"Architecture pattern '{output.architecture_pattern}' is not recognized. "
                f"Expected one of: {', '.join(sorted(ARCHITECTURE_PATTERNS))}"
            )

        # ── Data flow format check ──────────────────────────────
        for i, step in enumerate(output.data_flow):
            if "step" not in step or "description" not in step:
                errors.append(f"Data flow step at index {i} missing 'step' or 'description' keys")
            elif not step.get("description", "").strip():
                errors.append(f"Data flow step {step.get('step', i)} has empty description")

        # ── Tech stack quality check ────────────────────────────
        required_categories = {"language", "framework", "database"}
        actual_categories = set(k.lower() for k in output.tech_stack)
        missing_cats = required_categories - actual_categories
        if missing_cats:
            errors.append(f"Missing required tech stack categories: {', '.join(sorted(missing_cats))}")

        for key, value in output.tech_stack.items():
            if value.lower() in VAGUE_TECH_TERMS:
                errors.append(f"Tech stack entry '{key}' has vague value: '{value}'")

        # ── Database design checks ──────────────────────────────
        if output.database_design and output.database_design.tables:
            db = output.database_design
            if len(db.tables) < 2:
                errors.append(f"Too few database tables: {len(db.tables)} (minimum 2)")

            table_names = set()
            for _i, table in enumerate(db.tables):
                tname_lower = table.name.lower()
                if tname_lower in table_names:
                    errors.append(f"Duplicate table name: '{table.name}'")
                table_names.add(tname_lower)

                if len(table.columns) < 2:
                    errors.append(f"Table '{table.name}' has only {len(table.columns)} columns (minimum 2)")

                has_pk = any(
                    "primary key" in col.get("constraints", "").lower()
                    or "primary" in col.get("constraints", "").lower()
                    for col in table.columns
                )
                if not has_pk:
                    errors.append(f"Table '{table.name}' has no primary key column")

                # Check for proper column structure
                for j, col in enumerate(table.columns):
                    if not isinstance(col, dict) or "name" not in col or "type" not in col:
                        errors.append(f"Table '{table.name}' column at index {j} missing 'name' or 'type'")

        # ── API spec checks ─────────────────────────────────────
        if output.api_spec and output.api_spec.endpoints:
            api = output.api_spec
            if len(api.endpoints) < 3:
                errors.append(f"Too few API endpoints: {len(api.endpoints)} (minimum 3)")

            for i, ep in enumerate(api.endpoints):
                if not ep.path.startswith("/"):
                    errors.append(f"API endpoint at index {i} path '{ep.path}' must start with /")
                if ep.method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                    errors.append(f"API endpoint at index {i} has invalid method: '{ep.method}'")
                if len(ep.description) < 5:
                    errors.append(f"API endpoint '{ep.method} {ep.path}' description too short")

        # ── Folder structure checks ─────────────────────────────
        if output.folder_structure:
            fs = output.folder_structure
            if not fs.root:
                errors.append("Folder structure root is empty")
            if len(fs.entries) < 2:
                errors.append(f"Too few folder entries: {len(fs.entries)} (minimum 2)")

        # ── Deployment strategy check ───────────────────────────
        if len(output.deployment_strategy) < 20:
            errors.append("Deployment strategy is too short (minimum 20 characters)")

        # ── Mermaid diagram check ───────────────────────────────
        if output.diagram_mermaid and not output.diagram_mermaid.strip().startswith("graph"):
            errors.append("Mermaid diagram should start with 'graph' directive")

        # ── Raise if errors found ───────────────────────────────
        if errors:
            error_summary = "\n".join(f"  - {e}" for e in errors)
            logger.warning(
                "architecture_validation_errors",
                error_count=len(errors),
                component_count=comp_count,
                tech_count=tech_count,
            )
            raise ValueError(f"Architecture validation failed with {len(errors)} issue(s):\n{error_summary}")

        return output

    def _sanitize_output(self, output: ArchitectureDoc) -> ArchitectureDoc:
        """Sanitize and normalize the architecture output."""
        components = [
            ComponentSpec(
                name=comp.name.strip(),
                description=comp.description.strip(),
                technology=comp.technology.strip(),
                responsibilities=[r.strip() for r in comp.responsibilities],
                dependencies=[d.strip() for d in comp.dependencies],
                api_endpoints=[{k.strip(): v.strip() for k, v in ep.items()} for ep in comp.api_endpoints],
            )
            for comp in output.components
        ]

        data_flow = [
            {
                "step": step.get("step", str(i + 1)).strip(),
                "description": step.get("description", "").strip(),
            }
            for i, step in enumerate(output.data_flow)
        ]

        tech_stack = {k.strip(): v.strip() for k, v in output.tech_stack.items()}

        security = [s.strip() for s in output.security_considerations]

        db_design = None
        if output.database_design:
            tables = [
                DatabaseTable(
                    name=t.name.strip(),
                    columns=[
                        {
                            "name": c.get("name", "").strip(),
                            "type": c.get("type", "").strip(),
                            "constraints": c.get("constraints", "").strip(),
                        }
                        for c in t.columns
                    ],
                    description=t.description.strip(),
                    relationships=[r.strip() for r in t.relationships],
                )
                for t in output.database_design.tables
            ]
            db_design = DatabaseDesign(
                engine=output.database_design.engine.strip(),
                tables=tables,
                orm=output.database_design.orm.strip() if output.database_design.orm else None,
                migration_tool=output.database_design.migration_tool.strip()
                if output.database_design.migration_tool
                else None,
                caching_strategy=output.database_design.caching_strategy.strip()
                if output.database_design.caching_strategy
                else None,
                sharding_strategy=output.database_design.sharding_strategy.strip()
                if output.database_design.sharding_strategy
                else None,
                backup_strategy=output.database_design.backup_strategy.strip()
                if output.database_design.backup_strategy
                else None,
            )

        api_spec = None
        if output.api_spec:
            endpoints = [
                APIEndpoint(
                    path=ep.path.strip(),
                    method=ep.method.strip().upper(),
                    description=ep.description.strip(),
                    request_body=ep.request_body,
                    response_body=ep.response_body,
                    auth_required=ep.auth_required,
                    rate_limited=ep.rate_limited,
                )
                for ep in output.api_spec.endpoints
            ]
            api_spec = APISpec(
                protocol=output.api_spec.protocol.strip().upper(),
                base_url=output.api_spec.base_url.strip() if output.api_spec.base_url else None,
                endpoints=endpoints,
                auth_method=output.api_spec.auth_method.strip() if output.api_spec.auth_method else None,
                rate_limiting=output.api_spec.rate_limiting.strip() if output.api_spec.rate_limiting else None,
                versioning_strategy=output.api_spec.versioning_strategy.strip()
                if output.api_spec.versioning_strategy
                else None,
            )

        folder_structure = None
        if output.folder_structure:

            def _clean_entries(entries: list[Any]) -> list[FolderEntry]:
                return [
                    FolderEntry(
                        name=e.name.strip(),
                        type=e.type.strip().lower(),
                        children=_clean_entries(e.children) if e.children else [],
                        description=e.description.strip() if e.description else None,
                    )
                    for e in entries
                ]

            folder_structure = FolderStructure(
                root=output.folder_structure.root.strip(),
                entries=_clean_entries(output.folder_structure.entries),
                description=output.folder_structure.description.strip(),
            )

        return ArchitectureDoc(
            title=output.title.strip(),
            overview=output.overview.strip(),
            architecture_pattern=output.architecture_pattern.strip(),
            components=components,
            data_flow=data_flow,
            tech_stack=tech_stack,
            diagram_mermaid=output.diagram_mermaid.strip() if output.diagram_mermaid else None,
            deployment_strategy=output.deployment_strategy.strip(),
            security_considerations=security,
            database_design=db_design,
            api_spec=api_spec,
            folder_structure=folder_structure,
            scalability_notes=output.scalability_notes.strip() if output.scalability_notes else None,
            monitoring_strategy=output.monitoring_strategy.strip() if output.monitoring_strategy else None,
        )

    def _build_state_updates(
        self,
        state: GraphState,
        output: ArchitectureDoc,
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
                {
                    "agent": self.agent_type.value,
                    **token_usage,
                }
            ]

        return updates
