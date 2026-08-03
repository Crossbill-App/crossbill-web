# Global Rate Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an app-wide per-IP default rate limit so the entire `/api/v1/*` surface, the SPA catch-all, and the `/assets/*` mount are protected from scraper / scanner floods, while preserving the existing tighter per-route limits on auth endpoints.

**Architecture:**
- Replace today's three independent `Limiter()` instances (one each in `main.py`, `auth.py`, `users.py`) with a **single shared limiter** in a new module `backend/src/infrastructure/common/rate_limit.py`. SlowApi's per-route `@limiter.limit(...)` decorator only acts as an override for the *same* limiter instance — separate instances would stack the global default on top of per-route limits, which is not what we want.
- Configure the shared limiter with `default_limits=["300/minute"]` (configurable via env) and install `slowapi.middleware.SlowAPIMiddleware` so the default actually fires on routes that have no decorator (today nothing fires the default).
- Exempt `/health` so Railway/Docker health probes are never rate-limited.
- Existing real-client-IP fix (PR #340: `--proxy-headers --forwarded-allow-ips='*'` in `Dockerfile:72`) is already merged, so `get_remote_address` returns the true client IP behind Railway's edge proxy.

**Static asset behavior — important caveat:** SlowAPIMiddleware uses `_find_route_handler`, which only sees objects whose route has an `.endpoint` attribute. The `app.mount("/assets", StaticFiles(...))` in `main.py:405` produces a `starlette.routing.Mount` (no `.endpoint`), so `handler` resolves to `None` and `_should_exempt(...)` returns `True`. **`/assets/*` is therefore implicitly exempt from the limiter.** This is acceptable (assets are static, browser-cached, and Cloudflare absorbs floods upstream), and we explicitly verify it in the tests rather than try to subject `Mount`-served files to the limiter. The SPA catch-all `serve_spa` *is* a regular `@app.get(...)` route with an endpoint, so it remains subject to the default limit.

**Tech Stack:** Existing `slowapi>=0.1.9,<0.2.0` (already a backend dep). No new packages.

**Out of scope:**
- Cloudflare WAF (#343) and short-circuit scanner paths (#341) — separate tickets, deliberately complementary.
- Distributed/Redis-backed limiter storage. The default in-memory store is per-process; with Railway running 1 web container today this is fine. If we scale horizontally we need to move storage to Postgres or Redis — flagged in "Future considerations" at the end.

---

### Task 1: Add Rate-Limit Settings

**Files:**
- Modify: `backend/src/config.py`

- [ ] **Step 1: Add the new settings fields**

In `backend/src/config.py`, inside the `Settings` class — add these next to the other top-level fields (place them after the `CORS_ORIGINS` block, before `# Admin setup`):

```python
    # Rate limiting (per-IP, applied app-wide via slowapi)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "300/minute"
```

- [ ] **Step 2: Verify pyright passes**

Run: `cd backend && uv run pyright src/config.py`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add backend/src/config.py
git commit -m "feat(config): add RATE_LIMIT_ENABLED and RATE_LIMIT_DEFAULT settings"
```

---

### Task 2: Disable the Limiter in the Test Suite

**Why before the wiring change:** Once the SlowAPIMiddleware is installed in Task 4, every existing test that hammers an endpoint in a tight loop (e.g. fixtures that create many books) would start hitting the default 300/minute bucket because `httpx.AsyncClient` always reports the same client host. We pre-emptively disable the limiter for the existing tests, then in Task 7 we add a dedicated test file that re-enables it locally for the rate-limit assertions.

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Set the env var before app import**

In `backend/tests/conftest.py`, find the existing `os.environ.setdefault(...)` block at the top of the file (lines 8–14) and add one more line so the block reads:

```python
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault(
    "REFRESH_TOKEN_SECRET_KEY",
    "test-refresh-token-secret-key-at-least-32-bytes-long",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
```

The order matters: this must execute *before* the `from src.main import app` import further down in the file, because `Settings` is read at module import time.

- [ ] **Step 2: Run the full test suite as a sanity baseline**

Run: `cd backend && uv run pytest -x -q`
Expected: existing tests pass (rate limiter is currently a no-op anyway, so this is just verifying we didn't break import order).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: disable rate limiter in test environment"
```

---

### Task 3: Create the Shared Limiter Module

**Files:**
- Create: `backend/src/infrastructure/common/rate_limit.py`

- [ ] **Step 1: Write the module**

Create `backend/src/infrastructure/common/rate_limit.py`:

```python
"""Shared rate limiter instance used app-wide.

A single Limiter instance is exposed so that per-route ``@limiter.limit(...)``
decorators (e.g. on auth endpoints) and the global ``default_limits`` share
the same internal state. Using separate Limiter instances would cause the
global default to stack on top of per-route limits instead of being
overridden by them.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.RATE_LIMIT_DEFAULT],
    enabled=_settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
)
```

`get_remote_address` reads `request.client.host`, which uvicorn populates from `X-Forwarded-For` because we already pass `--proxy-headers --forwarded-allow-ips='*'` (see `Dockerfile:72`).

`headers_enabled=True` makes slowapi attach `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` to responses, which helps clients (and us) see how close they are to the bucket.

- [ ] **Step 2: Verify pyright + ruff pass on the new file**

Run: `cd backend && uv run pyright src/infrastructure/common/rate_limit.py && uv run ruff check src/infrastructure/common/rate_limit.py`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add backend/src/infrastructure/common/rate_limit.py
git commit -m "feat(rate-limit): add shared Limiter instance module"
```

---

### Task 4: Wire `main.py` to the Shared Limiter and Install Middleware

**Files:**
- Modify: `backend/src/main.py:18-20` (imports)
- Modify: `backend/src/main.py:167-169` (limiter construction)
- Modify: `backend/src/main.py:384-387` (`/health` endpoint)
- Modify: `backend/src/main.py` (add middleware registration alongside the existing security middleware)

- [ ] **Step 1: Replace the slowapi imports**

In `backend/src/main.py`, change the existing imports at lines 18–20 from:

```python
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
```

to:

```python
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.infrastructure.common.rate_limit import limiter
```

(`get_remote_address` is no longer needed in `main.py` — it's used inside the shared module. `Limiter` is no longer constructed here.)

- [ ] **Step 2: Replace the limiter construction**

In `backend/src/main.py`, change lines 167–169 from:

```python
# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

to:

```python
# Wire the shared rate limiter and install slowapi's middleware so
# `default_limits` apply to every route (not only those with an explicit
# `@limiter.limit(...)` decorator).
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
```

- [ ] **Step 3: Exempt `/health` from rate limiting**

In `backend/src/main.py`, find the existing `/health` endpoint (lines 384–387):

```python
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
```

Change it to:

```python
@app.get("/health")
@limiter.exempt  # type: ignore[misc]
async def health() -> dict[str, str]:
    """Health check endpoint. Exempt from rate limit so probes never trip it."""
    return {"status": "healthy"}
```

`@limiter.exempt` registers the route name in `limiter._exempt_routes`; the SlowAPIMiddleware short-circuits before checking limits for exempt routes (see `slowapi/middleware.py:_should_exempt`).

- [ ] **Step 4: Run pyright on main.py**

Run: `cd backend && uv run pyright src/main.py`
Expected: 0 errors. (If pyright complains about the unused `get_remote_address` import being missing from the shared module's surface, that's fine — main.py no longer needs it.)

- [ ] **Step 5: Run the full test suite**

Run: `cd backend && uv run pytest -x -q`
Expected: All pass. Because `RATE_LIMIT_ENABLED=false` is set in `conftest.py`, the limiter is disabled and the middleware is a fast pass-through (`if not limiter.enabled: return await call_next(request)`).

- [ ] **Step 6: Commit**

```bash
git add backend/src/main.py
git commit -m "feat(rate-limit): install SlowAPIMiddleware and exempt /health"
```

---

### Task 5: Migrate `auth.py` to the Shared Limiter

**Files:**
- Modify: `backend/src/infrastructure/identity/routers/auth.py:9-10` (imports)
- Modify: `backend/src/infrastructure/identity/routers/auth.py:32` (delete local limiter)

- [ ] **Step 1: Replace the slowapi imports**

In `backend/src/infrastructure/identity/routers/auth.py`, change lines 9–10 from:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
```

to:

```python
from src.infrastructure.common.rate_limit import limiter
```

- [ ] **Step 2: Delete the local limiter construction**

In `backend/src/infrastructure/identity/routers/auth.py`, delete line 32:

```python
limiter = Limiter(key_func=get_remote_address)
```

(The decorators `@limiter.limit("5/minute")` on `login` and `@limiter.limit("10/minute")` on `refresh` keep working — they now reference the shared `limiter` imported at the top.)

- [ ] **Step 3: Verify pyright + ruff pass**

Run: `cd backend && uv run pyright src/infrastructure/identity/routers/auth.py && uv run ruff check src/infrastructure/identity/routers/auth.py`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/infrastructure/identity/routers/auth.py
git commit -m "refactor(auth): use shared rate limiter instance"
```

---

### Task 6: Migrate `users.py` to the Shared Limiter

**Files:**
- Modify: `backend/src/infrastructure/identity/routers/users.py:4-5` (imports)
- Modify: `backend/src/infrastructure/identity/routers/users.py:23` (delete local limiter)

- [ ] **Step 1: Replace the slowapi imports**

In `backend/src/infrastructure/identity/routers/users.py`, change lines 4–5 from:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
```

to:

```python
from src.infrastructure.common.rate_limit import limiter
```

- [ ] **Step 2: Delete the local limiter construction**

In `backend/src/infrastructure/identity/routers/users.py`, delete line 23:

```python
limiter = Limiter(key_func=get_remote_address)
```

- [ ] **Step 3: Verify pyright + ruff pass**

Run: `cd backend && uv run pyright src/infrastructure/identity/routers/users.py && uv run ruff check src/infrastructure/identity/routers/users.py`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/infrastructure/identity/routers/users.py
git commit -m "refactor(users): use shared rate limiter instance"
```

---

### Task 7: Add Integration Tests

We need four behavioral assertions:
1. The global default fires on a previously unprotected route once the per-IP bucket is exceeded.
2. A per-route limit (e.g. `@limiter.limit("5/minute")` on `/api/v1/auth/login`) still applies and overrides the default — i.e. login is *tighter*, not looser, than the default.
3. `/health` is exempt and never returns 429.
4. The SPA catch-all (`@app.get("/{full_path:path}") -> serve_spa`) IS subject to the default limit. This is the route most exposed to vulnerability scanners — it currently serves `index.html` at 200 OK for any unknown path, so a scanner can cheaply burn CPU/bandwidth there. (We do not test that `/assets/*` is limited because it isn't — see the "Static asset behavior" note in Architecture.)

**Files:**
- Create: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/test_rate_limit.py`:

```python
"""Integration tests for the global per-IP rate limiter.

The test environment disables the limiter by default (see conftest.py) so
existing tests can hammer endpoints freely. This file re-enables it with a
tiny bucket so we can assert the 429 behaviour without making 300+ calls.

The fixture composes on top of the existing ``client`` fixture so it
inherits the test DB session and authentication overrides — we only mutate
the limiter on the same app instance and restore it on teardown.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from slowapi.util import get_remote_address
from slowapi.wrappers import LimitGroup

from src.main import app


@pytest.fixture
async def rate_limited_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Re-enable the limiter at 3/minute on the shared app and yield the test client.

    Depends on the conftest ``client`` fixture so DB and auth overrides are in
    place. We restore the limiter's original ``enabled`` flag and
    ``_default_limits`` on teardown to avoid cross-test pollution.
    """
    limiter = app.state.limiter

    original_enabled = limiter.enabled
    original_defaults = list(limiter._default_limits)

    # slowapi stores defaults as LimitGroup objects (NOT Limit objects).
    # _check_request_limit does ``itertools.chain(*self._default_limits)`` and
    # iterating a LimitGroup yields parsed Limit instances, so we must hand it
    # a LimitGroup here — Limit alone would explode at iteration time.
    limiter.enabled = True
    limiter._default_limits = [
        LimitGroup(
            "3/minute",
            get_remote_address,
            None,
            False,
            None,
            None,
            None,
            1,
            False,
        )
    ]
    limiter.reset()

    yield client

    limiter.enabled = original_enabled
    limiter._default_limits = original_defaults
    limiter.reset()


async def test_default_limit_triggers_429_on_unprotected_route(
    rate_limited_client: AsyncClient,
) -> None:
    """The 4th request from the same IP to a route with no per-route limit is 429."""
    # /api/v1/ has no per-route decorator, so it falls through to the default bucket.
    for _ in range(3):
        response = await rate_limited_client.get("/api/v1/")
        assert response.status_code == 200, response.text

    response = await rate_limited_client.get("/api/v1/")
    assert response.status_code == 429
    body = response.json()
    assert body["error"] == "rate_limit_exceeded"


async def test_spa_catch_all_is_subject_to_default_limit(
    rate_limited_client: AsyncClient,
) -> None:
    """The SPA catch-all (serve_spa) is the main scanner-amplification surface.

    Note: this test only runs meaningfully when the static directory exists
    (i.e. the frontend has been built into ``backend/static``). When it
    doesn't exist the catch-all isn't registered at all — skip in that case.
    """
    from src.main import STATIC_DIR

    if not STATIC_DIR.exists():
        pytest.skip("static dir not present — SPA catch-all not registered")

    for _ in range(3):
        response = await rate_limited_client.get("/some-arbitrary-spa-path")
        assert response.status_code == 200

    response = await rate_limited_client.get("/another-spa-path")
    assert response.status_code == 429


async def test_health_endpoint_is_exempt(
    rate_limited_client: AsyncClient,
) -> None:
    """/health is exempt — health probes must never get 429."""
    for _ in range(10):  # well above the 3/minute default
        response = await rate_limited_client.get("/health")
        assert response.status_code == 200


async def test_per_route_limit_overrides_default(
    rate_limited_client: AsyncClient,
) -> None:
    """/api/v1/auth/login has @limiter.limit('5/minute') — its own bucket, not the default 3/minute.

    We exhaust the login bucket (5 attempts -> 6th is 429). This proves that the
    per-route decorator on auth.login uses the same Limiter instance as the
    default; otherwise the default's 3/minute bucket would have triggered first
    on the 4th attempt.
    """
    # Each request returns 401 (bad creds) but still counts against the bucket.
    for i in range(5):
        response = await rate_limited_client.post(
            "/api/v1/auth/login",
            data={"username": "no-such-user@test.com", "password": "wrong"},
        )
        assert response.status_code == 401, f"attempt {i + 1}: {response.text}"

    response = await rate_limited_client.post(
        "/api/v1/auth/login",
        data={"username": "no-such-user@test.com", "password": "wrong"},
    )
    assert response.status_code == 429
```

- [ ] **Step 2: Run the new test file in isolation first**

Run: `cd backend && uv run pytest tests/test_rate_limit.py -v`
Expected: All 3 tests pass.

If `test_per_route_limit_overrides_default` fails with 429 on the 4th login attempt instead of the 6th, that means the per-route decorator and the default limit are using different `Limiter` instances and stacking — go back to Tasks 5 and 6 and verify the local `Limiter()` constructions were actually removed.

- [ ] **Step 3: Run the full test suite to make sure no other test was broken by the limiter being mutated mid-session**

Run: `cd backend && uv run pytest -x -q`
Expected: All pass. The fixture restores `enabled` and `_default_limits` to their originals on teardown, so cross-test pollution should not occur — but verify.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_rate_limit.py
git commit -m "test(rate-limit): add integration tests for global default and exemptions"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run pyright on the full backend**

Run: `cd backend && uv run pyright`
Expected: 0 errors (or no *new* errors compared to baseline on `main`).

- [ ] **Step 2: Run ruff on the full backend**

Run: `cd backend && uv run ruff check src tests`
Expected: 0 errors.

- [ ] **Step 3: Run the full test suite one final time**

Run: `cd backend && uv run pytest -q`
Expected: All pass.

- [ ] **Step 4: Manual smoke check that `default_limits` actually attaches to non-decorated routes**

Run: `cd backend && uv run python -c "from src.main import app; lim = app.state.limiter; print('enabled=', lim.enabled, 'defaults=', [str(g.limit) for g in lim._default_limits])"`

Set `RATE_LIMIT_ENABLED=true` and `RATE_LIMIT_DEFAULT=42/minute` in your `.env`, then re-run. Expected output should include `enabled= True defaults= ['42 per 1 minute']`. Reset your `.env` after.

This catches misconfiguration where the env vars aren't actually flowing into the limiter.

---

## Future Considerations (do NOT implement now — just notes)

- **Distributed storage:** the in-memory store is per-process. If we ever run >1 web replica, each replica enforces its own bucket and the effective ceiling is N × 300/minute. Move to `storage_uri="redis://..."` or the Postgres-backed equivalent at that point.
- **Tighter unauthenticated bucket:** the ticket suggests "Optionally tighter for unauthenticated traffic." Implementing that requires either a custom `key_func` (mix IP + auth state) or a second limiter applied via middleware ordering. Defer until we see real abuse traffic shape — premature without data.
- **Static asset coverage:** `/assets/*` is implicitly exempt because slowapi's middleware can't resolve a `Mount` to an endpoint handler. Acceptable for now (cached, Cloudflare in front). If we ever need to limit asset abuse specifically, options are (a) wrap StaticFiles in a thin `APIRoute` so it has an `endpoint` slowapi can see, or (b) add a tiny ASGI middleware in front of the mount that does its own limiting.

## Pairs With

- **#340** (already merged): X-Forwarded-* trust → real client IP
- **#341**: short-circuit known scanner paths (returns 404 cheaply before limiter even runs)
- **#343**: Cloudflare WAF — absorbs gross floods upstream of this app-layer limiter
