from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_auth
from app.config import settings
from app.core.logging import get_logger
from app.db.repositories.project_repo import ProjectRepository
from app.db.session import get_db_session
from app.models.domain.enums import ProjectStatus
from app.models.schemas.requests import (
    CreateProjectRequest,
    ExportProjectRequest,
    RefineProjectRequest,
)
from app.models.schemas.responses import (
    CreateProjectResponse,
    PaginatedResponse,
    ProjectDetailResponse,
    ProjectSummaryResponse,
)
from app.worker.tasks import run_generation_pipeline

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(verify_auth)])


def _dispatch_pipeline(idea: str, project_id: str, constraints: dict | None = None) -> None:
    """Dispatch the generation pipeline - via Celery if available, otherwise skip."""
    if settings.DISABLE_CELERY:
        logger.warning(
            "celery_disabled_skipping_pipeline",
            project_id=project_id,
            idea_preview=idea[:100],
        )
        return
    try:
        run_generation_pipeline.delay(
            idea=idea,
            project_id=project_id,
            constraints=constraints,
        )
    except Exception as e:
        logger.error(
            "celery_dispatch_failed",
            project_id=project_id,
            error=str(e),
        )


@router.post("", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: CreateProjectRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CreateProjectResponse:
    """Submit a new software idea for autonomous generation.

    Creates a project record, then dispatches a Celery task to
    run the full LangGraph agent pipeline in the background.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.create(
        idea=request.idea,
        constraints=request.constraints,
        status=ProjectStatus.PENDING,
    )

    logger.info(
        "project_created",
        project_id=str(project.id),
        idea_preview=request.idea[:100],
    )

    # Dispatch async pipeline via Celery worker (or skip if disabled)
    _dispatch_pipeline(
        idea=request.idea,
        project_id=str(project.id),
        constraints=request.constraints,
    )

    return CreateProjectResponse(
        project_id=project.id,
        status=project.status.value,
        status_url=f"/api/v1/projects/{project.id}",
    )


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse:
    """List all projects with pagination and optional status filter."""
    project_repo = ProjectRepository(session)

    filters = {}
    if status_filter:
        filters["status"] = status_filter

    skip = (page - 1) * page_size
    projects = await project_repo.list(skip=skip, limit=page_size, **filters)
    total = await project_repo.count(**filters)

    items = [
        ProjectSummaryResponse(
            id=p.id,
            idea=p.idea[:200],
            status=p.status.value if hasattr(p.status, "value") else p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Get project details including all generated artifacts."""
    project_repo = ProjectRepository(session)
    project = await project_repo.get_with_artifacts(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    artifacts: dict[str, dict] = {}
    for artifact in project.artifacts:
        artifacts[artifact.artifact_type] = artifact.content

    return ProjectDetailResponse(
        id=project.id,
        idea=project.idea,
        constraints=project.constraints,
        status=project.status.value if hasattr(project.status, "value") else project.status,
        requirements=artifacts.get("requirements"),
        architecture=artifacts.get("architecture"),
        source_code=artifacts.get("source_code"),
        test_suite=artifacts.get("test_suite"),
        documentation=artifacts.get("documentation"),
        review_report=artifacts.get("code_review"),
        created_at=project.created_at,
        updated_at=project.updated_at,
        completed_at=project.completed_at,
    )


@router.post("/{project_id}/refine", response_model=CreateProjectResponse)
async def refine_project(
    project_id: UUID,
    request: RefineProjectRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CreateProjectResponse:
    """Submit feedback to refine an existing project.

    Updates the project status to 'refining' and re-dispatches
    the pipeline with the original idea plus user feedback.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    project.status = ProjectStatus.REFINING
    await session.flush()

    logger.info(
        "project_refinement_initiated",
        project_id=str(project_id),
        feedback_preview=request.feedback[:100],
    )

    # Re-dispatch pipeline with original idea + feedback (or skip if disabled)
    _dispatch_pipeline(
        idea=f"{project.idea}\n\nFeedback: {request.feedback}",
        project_id=str(project_id),
        constraints=project.constraints,
    )

    return CreateProjectResponse(
        project_id=project.id,
        status=ProjectStatus.REFINING.value,
        status_url=f"/api/v1/projects/{project.id}",
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a project and all its artifacts."""
    project_repo = ProjectRepository(session)
    deleted = await project_repo.delete(project_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    logger.info("project_deleted", project_id=str(project_id))


@router.get("/{project_id}/status")
async def get_project_status(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get the current status of a project generation."""
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return {
        "project_id": str(project.id),
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "idea": project.idea[:200],
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "completed_at": project.completed_at.isoformat() if project.completed_at else None,
    }


@router.post("/{project_id}/export")
async def export_project(
    project_id: UUID,
    request: ExportProjectRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Export a generated project to GitHub.

    Creates a repository and pushes all generated artifacts
    (requirements, architecture, source code, tests, documentation)
    as files.
    """
    from app.services.github_service import github_service

    project_repo = ProjectRepository(session)
    project = await project_repo.get_with_artifacts(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if project.status.value not in ("completed",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot export project with status '{project.status.value}'. "
                "Only completed projects can be exported."
            ),
        )

    # Build project_data dict from artifacts
    project_data: dict[str, Any] = {}
    for artifact in project.artifacts:
        artifact_type = artifact.artifact_type
        project_data[artifact_type] = artifact.content

    try:
        result = await github_service.export_project(
            project_id=str(project_id),
            project_data=project_data,
            repo_name=request.repository_name,
            organization=request.organization,
            private=request.private,
        )
        return result
    except Exception as e:
        from app.core.exceptions import AppException

        if isinstance(e, AppException):
            raise
        logger.error("export_failed", project_id=str(project_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Export failed: {str(e)}",
        ) from e
