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
- [x] **2.4** Documentation Agent: add minimal validation + few-shot prompt
    - Deep validation: non-empty README and setup_guide, minimum length checks (100/50 chars)
    - Sanitization: strips whitespace from all fields
    - Hooked sanitization via _build_state_updates override
    - Few-shot prompt: added good/bad JSON examples
    - 12 new unit tests covering validation and sanitization
- [x] **2.5** Add dedicated unit test files for all four agents (completed within 2.1–2.4 above)
    - `tests/unit/test_developer_agent.py` — 20 tests
    - `tests/unit/test_tester_agent.py` — 19 tests
    - `tests/unit/test_code_review_agent.py` — 22 tests
    - `tests/unit/test_documentation_agent.py` — 12 tests
    - Total: 73 new tests for all four agents

---

## Phase 3 — Security and production hardening

- [x] **3.1** Wire existing JWT/API-key dependencies into middleware protecting project routes
- [x] **3.2** Implement rate-limiting middleware using existing RateLimitException and RATE_LIMIT_* settings
    - Added `RateLimitMiddleware` to `app/core/middleware.py`: in-memory sliding-window per-IP rate limiter
    - Sends `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers
    - Returns 429 with JSON body when limit exceeded
    - Skipped when `settings.ENVIRONMENT == "test"` (set in conftest.py to protect other tests)
    - 6 new tests covering: under-limit passes, 429 on exceed, headers present, window reset, test-env skip, zero-remaining
- [x] **3.3** Add production Dockerfile target / reverse proxy story
    - Backend Dockerfile production CMD switched to gunicorn+uvicorn workers
    - `docker/nginx/api.conf` — production nginx reverse proxy with SSL, rate limiting (30r/s), security headers
    - `docker/nginx/Dockerfile` — minimal nginx image for the reverse proxy
    - `docker-compose.prod.yml` — overlay that adds reverse-proxy service and un-exposes API port
    - `Makefile` — `ssl-cert`, `prod-*` targets for full production stack
- [x] **3.4** Add secrets-management story beyond plain .env
    - `config.py`: added `DOCKER_SECRET_MAP` + `_load_docker_secrets()` — reads from `/run/secrets/<name>` with fallback to `.env` and env vars
    - `.env.production.template` — clean template with no real secrets, documents Docker secret alternative
    - `docker-compose.secrets.yml` — overlay showing how to mount Docker secrets for api + worker services
    - 9 new tests covering: skipped dir, override, whitespace stripping, non-secret fields, key coverage, model_post_init hook

---

## Phase 4 — CI/CD

- [x] **4.1** Add GitHub Actions workflow: Postgres + Redis services, alembic upgrade, pytest, ruff check, frontend build
    - `.github/workflows/ci.yml` — full CI pipeline on push/PR to main
    - Services: PostgreSQL (ai_dev_team + ai_dev_team_test), Redis
    - Steps: ruff → pytest (with coverage) → mypy → frontend build
- [ ] **4.2** Gate merges to main on workflow passing — *GitHub repo setting (branch protection), cannot be done in code. Configure via Settings > Branches > Add rule > Require status checks to pass before merging.*
- [x] **4.3** Add Docker image build workflow for backend and frontend
    - `.github/workflows/docker-build.yml` — builds + pushes to ghcr.io on main push and version tags
    - Uses docker/metadata-action for semver + SHA tagging, GHA cache layers

---

## Phase 5 — Real-time updates, exports, and other missing features

- [x] **5.1** Wire EventPublisher to Redis pub/sub + add WebSocket endpoint
    - `events.py`: `EventPublisher.publish()` now uses `redis.asyncio` to publish to Redis pub/sub
    - `ws.py`: New WebSocket endpoint at `/api/v1/projects/{project_id}/ws` subscribes to Redis channel and forwards events to client
    - `tasks.py`: Publishes `pipeline_started`/`pipeline_completed`/`pipeline_error` events
    - `nodes.py`: Each agent node publishes `agent_started`/`agent_completed`/`agent_error` events
- [x] **5.2** Implement GitHub export feature behind ExportProjectRequest schema
    - `services/github_service.py` — creates GitHub repos, pushes all artifacts as files
    - `POST /api/v1/projects/{id}/export` — endpoint using `ExportProjectRequest`
- [x] **5.3** Add Prometheus + Grafana to docker-compose.yml
    - `docker/prometheus/prometheus.yml` — scrapes API, postgres, redis
    - `docker/grafana/datasources/` — Prometheus datasource provisioning
    - `docker/grafana/dashboards/` — dashboard provider config
    - `docker-compose.yml` — added `prometheus` and `grafana` services
    - `server.py` — conditional `prometheus-fastapi-instrumentator` at `/metrics`
    - Added `prometheus-fastapi-instrumentator` to `base.txt`
- [x] **5.4** Clean up dead scaffolding (docker/, scripts/, src/) — removed empty scripts/ and src/
- [x] **5.5** Consolidate duplicate dependency declarations (root requirements.txt vs backend/requirements/) — removed root requirements.txt
- [x] **5.6** Fix stale docstring in pipeline.py (resume_from_checkpoint still references invoke) — invoke → ainvoke

---

## Phase 6 — Frontend polish

- [x] **6.1** Mobile-responsive sidebar with hamburger toggle, overlay, and slide transition
- [x] **6.2** Switch MonitorPage/ResultsPage from polling to WebSocket subscription
    - New `useWebSocket` generic hook with reconnection logic
    - `useProjectDetail` and `useProjectStatus` use WS events to invalidate react-query cache
    - Slow 30s fallback poll for WS-disconnect resilience
    - nginx config updated with WebSocket upgrade headers and 1h timeout
    - MonitorPage shows "live updates" indicator
- [x] **6.3** Use `VITE_API_BASE_URL` env var in `api.ts` instead of hardcoded `/api/v1`

---

## Phase 7 — Pre-release hardening

- [x] **7.1** Full-stack re-verification and fix deployment bugs
    - Fixed `STORAGE_ROOT` path resolution in Docker (was resolving to `/`)
    - Fixed named volume directory permissions (pre-create + chown before `USER app`)
    - Fixed `prometheus-fastapi-instrumentator` v7 incompatibility with Starlette → upgraded to v8
    - Rebuilt Docker stack from clean state, Alembic migrations applied
    - Verified auth: no-credentials → 401, valid API key → 201
    - Pipeline runs through Celery + LangGraph (Groq rate-limited but code path verified)
    - Rate-limit middleware confirmed active (X-RateLimit headers present)
    - Frontend: fixed nginx.conf WS proxy headers, fixed health check IPv6 issue
- [x] **7.2** Prove branch protection — open PR with deliberate test failure, verify CI blocks merge, fix and merge
    - PR #1 opened with deliberate test failure (af2d438)
    - CI correctly failed on first commit
    - Fix commits pushed: ruff (6e79739), mypy (7df973f–89ee549)
    - CI passed on run #11 after all fixes
    - Merged to main (89ee549)
    - Branch protection configured: requires review, CI status checks pass
    - Note: repo owner can bypass; enforcement applies to other contributors
- [ ] **7.3** Replace placeholder secrets (SECRET_KEY, API_KEY)
- [ ] **7.4** Consolidate historical report files into docs/history/
- [ ] **7.5** Update README.md with current setup, auth, test suite, CI instructions
- [ ] **7.6** Tag v1.0.0 release
