# Progress — AI Software Development Team

> **Session start ritual:** Read this file and `git log --oneline -30` before doing anything else. Confirm what's already complete. Work on the next unchecked task only. Update this file and commit immediately after finishing each task.

---

## Cross-cutting

- [x] PROGRESS.md created — session continuity plan in place

---

## Phase 0 — Get it running for real

- [ ] **0.1** Fix config key mismatch (CHROMADB_HOST vs CHROMA_HOST) in `.env.example`
- [ ] **0.2** `cp .env.example .env` and fill in OPENAI_API_KEY, DATABASE_URL, REDIS_URL, CHROMA_HOST
- [ ] **0.3** `make dev-up` — bring up postgres/redis/chromadb via docker-compose
- [ ] **0.4** `cd backend && alembic upgrade head` against real PostgreSQL — verify success
- [ ] **0.5** Start API + Celery worker, submit test idea via `POST /api/v1/projects`
- [ ] **0.6** Fix whatever breaks during end-to-end run
- [ ] **0.7** Verify generated code/manifest land in `storage/generated_code/` and `storage/manifests/`

---

## Phase 1 — Make test suite trustworthy

- [ ] **1.1** Switch integration/API tests to run against real PostgreSQL (testcontainers or docker-compose test service)
- [ ] **1.2** Fix passlib + bcrypt incompatibility on Python 3.13
- [ ] **1.3** Add at least one true end-to-end test (API → Celery → LangGraph → DB → disk)
- [ ] **1.4** Push coverage from 78% toward 80%+ (focus: server.py, middleware.py, session.py, tasks.py, projects.py)

---

## Phase 2 — Strengthen the four weak agents

- [ ] **2.1** Developer Agent: add deep validation, sanitization, few-shot prompt
- [ ] **2.2** Tester Agent: validate tests reference real functions/files, enforce coverage target
- [ ] **2.3** Code Review Agent: validate review content quality (specific findings tied to files/lines)
- [ ] **2.4** Documentation Agent: add minimal validation + few-shot prompt
- [ ] **2.5** Add dedicated unit test files for all four agents

---

## Phase 3 — Security and production hardening

- [ ] **3.1** Wire existing JWT/API-key dependencies into middleware protecting project routes
- [ ] **3.2** Implement rate-limiting middleware using existing RateLimitException and RATE_LIMIT_* settings
- [ ] **3.3** Add production Dockerfile target / reverse proxy story
- [ ] **3.4** Add secrets-management story beyond plain .env

---

## Phase 4 — CI/CD

- [ ] **4.1** Add GitHub Actions workflow: Postgres + Redis services, alembic upgrade, pytest, ruff check, frontend build
- [ ] **4.2** Gate merges to main on workflow passing
- [ ] **4.3** Add Docker image build workflow for backend and frontend

---

## Phase 5 — Real-time updates, exports, and other missing features

- [ ] **5.1** Wire EventPublisher to Redis pub/sub + add WebSocket endpoint
- [ ] **5.2** Implement GitHub export feature behind ExportProjectRequest schema
- [ ] **5.3** Add Prometheus + Grafana to docker-compose.yml
- [ ] **5.4** Clean up dead scaffolding (docker/, scripts/, src/)
- [ ] **5.5** Consolidate duplicate dependency declarations (root requirements.txt vs backend/requirements/)
- [ ] **5.6** Fix stale docstring in pipeline.py (resume_from_checkpoint still references invoke)

---

## Phase 6 — Frontend polish

- [ ] **6.1** Make sidebar/layout responsive on mobile (beyond hidden/flex placeholder)
- [ ] **6.2** Switch MonitorPage and ResultsPage from polling to WebSocket subscription
- [ ] **6.3** Add production environment config (API base URL not hardcoded to localhost:8000)
