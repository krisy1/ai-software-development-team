# Progress — AI Software Development Team

> **Session start ritual:** Read this file and `git log --oneline -30` before doing anything else. Confirm what's already complete. Work on the next unchecked task only. Update this file and commit immediately after finishing each task.

---

## Cross-cutting

- [x] PROGRESS.md created — session continuity plan in place

---

## Phase 0 — Get it running for real

- [x] **0.1** Fix config key mismatch (CHROMADB_HOST vs CHROMA_HOST) in `.env.example` — already fixed, both use `CHROMA_HOST`
- [x] **0.2** `.env` created with Groq API key, added `OPENAI_BASE_URL` config for provider-agnostic LLM support
- [x] **0.3** `make docker-infra-up` — postgres/redis/chromadb up and healthy
- [x] **0.4** `alembic upgrade head` — migration applied: 3 tables (projects, project_artifacts, agent_executions) + alembic_version
- [x] **0.5** Start API + Celery worker, submit test idea via `POST /api/v1/projects`
- [x] **0.6** Fix whatever breaks during end-to-end run
    - 0.6a: Celery worker agent registry not initialized → `worker_process_init` signal + module reference fix in `nodes.py`
    - 0.6b: `module 'langchain' has no attribute 'debug'` → upgraded `langchain-core` from 0.3.86 to 1.4.8
    - 0.6c: Groq model `llama3-70b-8192` decommissioned → switched to `llama-3.3-70b-versatile`
- [x] **0.7** Verify end-to-end pipeline execution
    - Pipeline compiles (9 nodes), agents execute, LLM calls succeed (real Groq API calls)
    - Pipeline completes with proper error handling when an agent step fails
    - Artifact/DB persistence works but skipped when requirements agent fails early
    - Remaining issue: Requirements Agent user-story format validation too strict → tracked in Phase 2

---

## Phase 1 — Make test suite trustworthy

- [x] **1.1** Switch integration/API tests to run against real PostgreSQL (docker-compose test service)
- [x] **1.2** Fix passlib + bcrypt incompatibility on Python 3.13
- [x] **1.3** Add at least one true end-to-end test (API → Celery → LangGraph → DB → disk)
- [x] **1.4** Push coverage from 79% to 81% (focus: server.py, middleware.py, session.py, tasks.py, projects.py)
    - Added `tests/unit/test_session.py` — get_db_session rollback/commit paths (session.py 47%→100%)
    - Added `tests/unit/test_middleware.py` — middleware dispatch via TestClient (middleware.py 58%→100%)
    - Added `tests/unit/test_server.py` — health check + exception handler (server.py 57%→62%)
    - Added LLM init path test to `test_worker_tasks.py` (tasks.py 93%→100%)
    - Fixed E2E test `_clean_storage` fixture: duplicate path entries caused `shutil.rmtree` destroying subdirs
    - Overall: 79%→81% (432→409 missing), 293→301 tests

---

## Phase 2 — Strengthen the four weak agents

- [x] **2.1** Developer Agent: add deep validation, sanitization, few-shot prompt
    - Deep validation: checks empty root, absolute/traversal paths, empty content, duplicate paths, missing language, missing required files (README.md, requirements.txt)
    - Sanitization: strips whitespace, normalizes language to lowercase, deduplicates by path, sorts files, lowercases+kebabifies root name
    - Few-shot prompt: added good/bad JSON examples to system prompt
    - 20 new unit tests covering validate, sanitize, build_state_updates, build_user_prompt
- [x] **2.2** Tester Agent: validate tests reference real functions/files, enforce coverage target
    - Deep validation: missing framework, low coverage target (<0.8), empty code/file_path, duplicate test names, invalid type
    - Sanitization: strips whitespace, normalizes backslashes, deduplicates by name, enforces min coverage_target=0.8
    - Hooked sanitization via _build_state_updates override
    - Few-shot prompt: added good/bad JSON examples
    - 19 new unit tests covering all validation rules and sanitization
- [x] **2.3** Code Review Agent: validate review content quality (specific findings tied to files/lines)
    - Deep validation: score range, non-empty summary, min 3 strengths/weaknesses, no empty items,
      comment file_path/line_start/line_end/severity/message validation, valid severity values (critical/warning/info)
    - Sanitization: clamps score to [0,10], normalizes severity, fixes line_end < line_start, strips empty items
    - Hooked sanitization via _build_state_updates override
    - Few-shot prompt: added good/bad JSON examples
    - 22 new unit tests covering all validation rules and sanitization
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
