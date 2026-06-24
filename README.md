# AI Software Development Team

A multi-agent AI system that simulates a complete software development team. Given a software idea, the system autonomously generates requirements, architecture, source code, tests, and documentation via a LangGraph pipeline.

## Architecture

Six specialized AI agents collaborate via a LangGraph pipeline:

1. **Requirements Agent** — Produces structured PRD/SRS documents
2. **Architect Agent** — Designs system architecture with component specs
3. **Developer Agent** — Generates complete, working source code
4. **Tester Agent** — Creates unit and integration test suites
5. **Code Review Agent** — Reviews code quality and suggests improvements
6. **Documentation Agent** — Generates README, API docs, and setup guides

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL, Redis, ChromaDB)
- An LLM API key (Groq, OpenAI, or any OpenAI-compatible provider)

### Setup

```bash
# 1. Clone and configure environment
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, SECRET_KEY, API_KEY
#   SECRET_KEY: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
#   API_KEY:    python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Start infrastructure (PostgreSQL, Redis, ChromaDB)
make docker-infra-up

# 3. Install dependencies
make dev

# 4. Run database migrations
make migrate

# 5. Start the API
make api-start

# 6. (Optional) Start the Celery worker for async pipeline execution
make worker-start
```

### Using Docker (full stack)

```bash
make docker-up
```

## Authentication

The API supports two authentication methods:

- **API Key**: Pass `X-API-Key: <your-api-key>` header (matches `API_KEY` env var)
- **JWT Token**: Obtain via `POST /api/v1/auth/login` and pass `Authorization: Bearer <token>`

Requests without valid credentials receive a `401 Unauthorized` response.

### Rate Limiting

API endpoints are rate-limited (default: 100 requests/minute/IP). Rate limit headers are included in responses:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/projects` | Create a new project from an idea |
| `GET` | `/api/v1/projects` | List all projects |
| `GET` | `/api/v1/projects/{id}` | Get project details |
| `POST` | `/api/v1/projects/{id}/export` | Export project to GitHub |
| `WS` | `/api/v1/projects/{id}/ws` | WebSocket for real-time updates |
| `GET` | `/health` | Health check |

## Running Tests

```bash
# Unit tests (fast, no DB required)
cd backend && python -m pytest tests/unit/ -v

# Integration tests (require PostgreSQL)
cd backend && python -m pytest tests/integration/ -v

# All tests with coverage
cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

### Test Infrastructure

- **Unit tests**: 389 tests, no external dependencies
- **Integration tests**: require PostgreSQL (`ai_dev_team_test` database)
- Test settings are isolated via `ENVIRONMENT=test` env var

## CI/CD

- **CI**: GitHub Actions runs on push/PR to `main` — ruff, pytest (with coverage), mypy, frontend build
- **CD**: Docker images built and pushed to `ghcr.io` on version tags
- **Branch Protection**: `main` requires passing CI checks and review

## Code Quality

- **Ruff**: Python linting and formatting (`ruff check app/ tests/`)
- **Mypy**: Static type checking with strict mode (`mypy app/ --ignore-missing-imports`)
- **Pytest**: Unit + integration tests with coverage reporting

## Tech Stack

- **Backend**: Python 3.12, FastAPI, LangGraph, SQLAlchemy 2.0, Pydantic 2
- **Database**: PostgreSQL 16, ChromaDB (vector store), Redis (queue + pub/sub)
- **Queue**: Celery (async pipeline execution)
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Infrastructure**: Docker Compose, nginx reverse proxy, Prometheus, Grafana
- **LLM**: OpenAI-compatible API (Groq, OpenAI, etc.)

## Documentation

- [Software Requirements](docs/01-software-requirements-specification.md)
- [Architecture Design](docs/02-architecture-design-document.md)
- [Folder Structure](docs/03-folder-structure.md)
- [Development Roadmap](docs/04-development-roadmap.md)
- [Historical Reports](docs/history/) — archived documentation and reports

## License

MIT
