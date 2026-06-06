# P0 Fix Report: Async/Sync Mismatch in Celery Task

## Root Cause

`worker/tasks.py:68` called `pipeline.invoke(state)` (sync `invoke()`) but all 9 LangGraph nodes in `graph/nodes.py` are defined with `async def`, requiring `pipeline.ainvoke()` (async `ainvoke()`).

This caused a `RuntimeError: cannot call invoke() with async nodes` at runtime, blocking the entire generation pipeline.

## The Fix

**File:** `backend/app/worker/tasks.py` (line 70)

**Before:**
```python
final_state = pipeline.invoke(state)
```

**After:**
```python
final_state = asyncio.run(
    pipeline.ainvoke(
        state,
        config={"configurable": {"thread_id": project_id}},
    )
)
```

Key design decisions:
- `asyncio.run()` bridges the sync Celery worker to the async LangGraph runtime
- `config={"configurable": {"thread_id": project_id}}` is required because the pipeline is compiled with `MemorySaver` checkpointing
- The `@celery_app.task(bind=True)` decorator handles `self` injection automatically — calling `.run()` does NOT require passing `self` explicitly (Celery's `PromiseProxy` strips `self` from the public signature)

## Files Changed

| File | Change |
|------|--------|
| `backend/app/worker/tasks.py` | Line 70: `invoke()` → `ainvoke()` with `asyncio.run()` bridge |
| `backend/tests/unit/test_worker_tasks.py` | New file — 10 tests covering async invocation, config, return format, error handling, event loop safety |

## Test Results

- **10 new unit tests**: All passing (lint clean)
- **280 existing unit tests**: All passing (no regressions)
- **7 integration tests (pipeline)**: All passing
- **247 integration tests (API)**: Pre-existing errors — SQLite `JSONB` incompatibility in `db_session` fixture (unrelated to this fix)

## How the Tests Work

The Celery task is a `celery.local.PromiseProxy`, not a raw function. The `.run()` method auto-injects `self` (the task instance), so tests call:

```python
run_generation_pipeline.run(idea="...", project_id=str(uuid4()))
```

Request context is set up via:
```python
run_generation_pipeline.push_request(id="mock-task-id")
# ... test body ...
run_generation_pipeline.pop_request()
```

Retry behavior is tested by patching `run_generation_pipeline.retry` with `side_effect=Exception("retry-called")`.

## Remaining Risks

1. **Documentation debt:** `pipeline.py:resume_from_checkpoint()` docstring references `pipeline.invoke(state)` — this is documentation only (not a runtime blocker), but should be updated for accuracy.
2. **No integration test for the Celery task end-to-end:** Unit tests mock the pipeline. An integration test calling the actual pipeline through the Celery task would provide stronger coverage.
3. **No monitoring for `asyncio.run()` failures:** If `asyncio.run()` raises (e.g., event loop conflicts), the error surfaces as a generic `RuntimeError`. Consider wrapping in a more descriptive exception.
4. **Event loop in long-running workers:** `asyncio.run()` creates a new event loop each call. For high-throughput scenarios, consider reusing an event loop (but this is acceptable for the current architecture where tasks are long-running and infrequent).

## Verification

```bash
# Unit tests
cd backend && python -m pytest tests/unit/test_worker_tasks.py -v

# Full suite
cd backend && python -m pytest tests/unit/ -v

# Lint
cd backend && ruff check tests/unit/test_worker_tasks.py
```
