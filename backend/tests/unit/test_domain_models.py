from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.domain.project import (
    APIEndpoint,
    APISpec,
    CodeReviewReport,
    ComponentSpec,
    DatabaseDesign,
    DatabaseTable,
    Documentation,
    FolderEntry,
    FolderStructure,
    ProjectFile,
    ProjectTree,
    RequirementsDoc,
    ReviewComment,
    TestCase,
    TestSuite,
)


class TestRequirementsDoc:
    def test_valid_requirements(self):
        doc = RequirementsDoc(
            title="Test Project",
            purpose="A comprehensive task management system for agile teams with real-time collaboration features",
            scope="Full stack web application including REST API, WebSocket notifications, and modern frontend",
            functional_requirements=[
                {
                    "id": "FR-01",
                    "description": "Users shall register and authenticate using email and password",
                    "priority": "P0",
                },
                {
                    "id": "FR-02",
                    "description": "Users shall create tasks with title, description, and priority",
                    "priority": "P0",
                },
                {"id": "FR-03", "description": "Users shall update task status and reassign tasks", "priority": "P0"},
                {
                    "id": "FR-04",
                    "description": "Users shall add comments to tasks with markdown support",
                    "priority": "P1",
                },
                {
                    "id": "FR-05",
                    "description": "Users shall search and filter tasks by multiple criteria",
                    "priority": "P1",
                },
            ],
            non_functional_requirements=[
                {
                    "id": "NFR-01",
                    "description": "API responses under 200ms at 95th percentile under 1000 RPM",
                    "category": "performance",
                },
                {
                    "id": "NFR-02",
                    "description": "All passwords hashed with bcrypt, TLS 1.3 for all traffic",
                    "category": "security",
                },
                {
                    "id": "NFR-03",
                    "description": "System maintains 99.9% uptime during peak business hours",
                    "category": "availability",
                },
            ],
            user_stories=[
                {
                    "id": "US-01",
                    "description": "As a team member, I want to create and assign tasks so that work is organized",
                    "priority": "P0",
                },
                {
                    "id": "US-02",
                    "description": "As a manager, I want real-time task updates so I can track progress",
                    "priority": "P0",
                },
            ],
            constraints=["Must use Python 3.12"],
            assumptions=["Users have reliable internet access"],
        )
        assert doc.title == "Test Project"
        assert len(doc.functional_requirements) == 5

    def test_requirements_doc_is_frozen(self):
        doc = RequirementsDoc(
            title="Test Project",
            purpose="A comprehensive task management system for agile teams with real-time collaboration features",
            scope="Full stack web application including REST API, WebSocket notifications, and modern frontend",
            functional_requirements=[
                {
                    "id": "FR-01",
                    "description": "Users shall register and authenticate using email and password",
                    "priority": "P0",
                },
                {
                    "id": "FR-02",
                    "description": "Users shall create tasks with title, description, and priority",
                    "priority": "P0",
                },
                {"id": "FR-03", "description": "Users shall update task status and reassign tasks", "priority": "P0"},
                {
                    "id": "FR-04",
                    "description": "Users shall add comments to tasks with markdown support",
                    "priority": "P1",
                },
                {
                    "id": "FR-05",
                    "description": "Users shall search and filter tasks by multiple criteria",
                    "priority": "P1",
                },
            ],
            non_functional_requirements=[
                {
                    "id": "NFR-01",
                    "description": "API responses under 200ms at 95th percentile under 1000 RPM",
                    "category": "performance",
                },
                {
                    "id": "NFR-02",
                    "description": "All passwords hashed with bcrypt, TLS 1.3 for all traffic",
                    "category": "security",
                },
                {
                    "id": "NFR-03",
                    "description": "System maintains 99.9% uptime during peak business hours",
                    "category": "availability",
                },
            ],
            user_stories=[
                {
                    "id": "US-01",
                    "description": "As a team member, I want to create and assign tasks so that work is organized",
                    "priority": "P0",
                },
                {
                    "id": "US-02",
                    "description": "As a manager, I want real-time task updates so I can track progress",
                    "priority": "P0",
                },
            ],
            constraints=["Must use Python 3.12"],
            assumptions=["Users have reliable internet access"],
        )
        with pytest.raises(ValidationError):
            doc.title = "New Title"


class TestComponentSpec:
    def test_valid_component(self):
        component = ComponentSpec(
            name="Auth Service",
            description="Handles authentication",
            technology="FastAPI",
            responsibilities=["Login", "Register"],
            dependencies=["Database"],
            api_endpoints=[{"path": "/login", "method": "POST"}],
        )
        assert component.name == "Auth Service"

    def test_invalid_component_empty_name(self):
        with pytest.raises(ValidationError):
            ComponentSpec(
                name="",
                description="Short",
                technology="Python",
                responsibilities=["Do"],
            )


class TestDatabaseDesign:
    def test_valid_database_design(self):
        design = DatabaseDesign(
            engine="PostgreSQL 16",
            tables=[
                DatabaseTable(
                    name="users",
                    columns=[
                        {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
                        {"name": "email", "type": "VARCHAR", "constraints": "UNIQUE NOT NULL"},
                    ],
                    description="User accounts",
                ),
            ],
            orm="SQLAlchemy 2.0",
            migration_tool="Alembic",
        )
        assert design.engine == "PostgreSQL 16"
        assert len(design.tables) == 1
        assert design.tables[0].name == "users"

    def test_database_table_requires_columns(self):
        with pytest.raises(ValidationError):
            DatabaseTable(
                name="empty",
                columns=[],
                description="No columns",
            )

    def test_empty_tables_allowed_for_cli_tools(self):
        """CLI tools/libraries with no database: empty tables list is valid."""
        design = DatabaseDesign(
            engine="N/A (CLI tool)",
            tables=[],
        )
        assert len(design.tables) == 0

    def test_none_protocol_valid(self):
        """NONE protocol is valid for CLI tools with no API."""
        spec = APISpec(
            protocol="NONE",
            base_url=None,
            endpoints=[],
            auth_method=None,
        )
        assert spec.protocol == "NONE"
        assert spec.base_url is None
        assert len(spec.endpoints) == 0
        assert spec.auth_method is None


class TestAPISpec:
    def test_valid_api_spec(self):
        spec = APISpec(
            protocol="REST",
            base_url="/api/v1",
            endpoints=[
                APIEndpoint(path="/login", method="POST", description="User login", auth_required=False),
                APIEndpoint(path="/users", method="GET", description="List users", auth_required=True),
                APIEndpoint(path="/users/{id}", method="GET", description="Get user", auth_required=True),
            ],
            auth_method="JWT",
        )
        assert spec.protocol == "REST"
        assert len(spec.endpoints) == 3

    def test_invalid_method(self):
        with pytest.raises(ValidationError):
            APIEndpoint(path="/test", method="INVALID", description="Bad method")

    def test_path_must_start_with_slash(self):
        with pytest.raises(ValidationError):
            APIEndpoint(path="api/login", method="GET", description="Missing slash")


class TestFolderStructure:
    def test_valid_folder_structure(self):
        fs = FolderStructure(
            root="myproject",
            entries=[
                FolderEntry(
                    name="src",
                    type="directory",
                    children=[
                        FolderEntry(name="main.py", type="file", description="Entry point"),
                    ],
                ),
                FolderEntry(name="README.md", type="file"),
            ],
        )
        assert fs.root == "myproject"
        assert len(fs.entries) == 2

    def test_invalid_entry_type(self):
        with pytest.raises(ValidationError):
            FolderEntry(name="x", type="symlink")


class TestProjectTree:
    def test_valid_project_tree(self):
        tree = ProjectTree(
            root="my_project",
            files=[
                ProjectFile(
                    path="main.py",
                    content="print('hello')",
                    language="python",
                )
            ],
        )
        assert len(tree.files) == 1
        assert tree.files[0].path == "main.py"


class TestTestSuite:
    def test_valid_test_suite(self):
        suite = TestSuite(
            test_framework="pytest",
            test_cases=[
                TestCase(
                    name="test_login",
                    description="Tests user login",
                    file_path="tests/test_auth.py",
                    code="def test_login(): pass",
                )
            ],
        )
        assert suite.test_framework == "pytest"
        assert len(suite.test_cases) == 1


class TestCodeReviewReport:
    def test_valid_review(self):
        report = CodeReviewReport(
            summary="Good code overall",
            overall_score=8.5,
            comments=[
                ReviewComment(
                    file_path="main.py",
                    line_start=10,
                    line_end=12,
                    severity="warning",
                    message="Unused variable",
                )
            ],
            strengths=["Clean code"],
            weaknesses=["Missing tests"],
            security_concerns=["SQL injection"],
        )
        assert report.overall_score == 8.5
        assert len(report.comments) == 1

    def test_invalid_score_high(self):
        with pytest.raises(ValidationError):
            CodeReviewReport(
                summary="Bad",
                overall_score=15.0,
                comments=[],
                strengths=[],
                weaknesses=[],
                security_concerns=[],
            )


class TestDocumentation:
    def test_valid_docs(self):
        docs = Documentation(
            readme="# Project",
            setup_guide="pip install",
            api_docs="## API",
        )
        assert docs.readme == "# Project"
