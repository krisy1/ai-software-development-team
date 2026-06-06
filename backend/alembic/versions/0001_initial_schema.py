"""Initial database schema.

Creates all three core tables matching the SQLAlchemy models:

- projects          (ProjectModel)
- project_artifacts (ArtifactModel)
- agent_executions  (ExecutionModel)

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-06-06 12:45:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("idea", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "completed", "failed", "refining",
                name="project_status",
                create_constraint=True,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # --- project_artifacts ---
    op.create_table(
        "project_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_artifacts_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "agent_type", "revision",
            name="uq_artifact_revision",
        ),
    )
    op.create_index("ix_project_artifacts_id", "project_artifacts", ["id"])
    op.create_index("ix_project_artifacts_project_id", "project_artifacts", ["project_id"])
    op.create_index("ix_project_artifacts_agent_type", "project_artifacts", ["agent_type"])

    # --- agent_executions ---
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "input_tokens", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "output_tokens", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "duration_ms", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_executions_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_executions_id", "agent_executions", ["id"])
    op.create_index("ix_agent_executions_project_id", "agent_executions", ["project_id"])


def downgrade() -> None:
    op.drop_table("agent_executions")
    op.drop_table("project_artifacts")
    op.drop_table("projects")

    sa.Enum(
        "pending", "running", "completed", "failed", "refining",
        name="project_status",
    ).drop(op.get_bind())
