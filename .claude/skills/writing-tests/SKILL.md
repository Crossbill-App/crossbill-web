---
name: writing-tests
description: Backend testing policy — API-first tiering, assertion depth, and test-quality rules
---

# Backend testing policy

The verification weight of this suite is carried by the API-level tests that run through
the real stack (TestClient → router → use case → repository → in-memory SQLite).
Mutation testing confirmed this empirically: logic bugs that the unit tier misses are
caught at the API tier. Write tests accordingly.

## Default: an API test

New behavior means a new or extended API test in `backend/tests/test_*.py`, exercised
through the endpoint, not the internals.

## Unit tests must be earned

Write a unit test (`tests/unit/`) only for pure domain logic with real branching: value
objects, parsers, domain services (e.g. `PositionIndex`, `HighlightStyleResolver`).
Litmus test: can you enumerate meaningful input classes without mocking anything? If the
setup needs `AsyncMock`, the behavior belongs in an API test instead.

Do NOT write mock-based tests for thin orchestration (application-layer use cases). A
test asserting "the repository was called" mirrors the implementation: it breaks on
refactors and survives logic bugs — the inversion of what a test is for.

```python
# ✗ WRONG — tautological; verifies the mock you just configured
use_case = CreateNoteUseCase(note_repository=mock_repo)
await use_case.execute(command)
mock_repo.save.assert_called_once()

# ✓ CORRECT — the API test covers the same wiring with real behavior
response = client.post("/api/notes", json={"title": "..."})
assert response.status_code == 201
assert response.json()["title"] == "..."
```

## Assertion depth in API tests

- Assert the meaningful fields of the response body, never just the status code.
- For mutating endpoints, verify persistence with a follow-up read.
- Every new endpoint gets a user-isolation case: user B must get 404/403 on user A's
  resource. A dropped `user_id` filter is this app's worst realistic bug class, and only
  a deliberate test catches it.

## Prove the test can fail

After writing a test, temporarily break the code under test (invert the condition,
short-circuit the function), confirm the test fails, then revert the breakage. A test
that cannot fail is worse than no test. Corollary: include at least one input where the
expected output differs from the input — a test whose inputs are all fixed points of the
function under test verifies nothing.

## What not to test — and permission to delete

Do not test exception message wiring, framework behavior, or anything fully shadowed by
a stronger API test. When you find a weak test (assertion-free, tautological, fully
shadowed), delete it. Fewer strong tests beat many weak ones.

## Mechanics

- Keep individual test cases short; share setup via fixtures, reusing `tests/conftest.py`
  fixtures before adding new ones.
- Run the full suite before declaring work done: `cd backend && uv run pytest`.
- Periodic quality audit: `make mutation-test` (mutmut over `src/domain/`). Surviving
  mutants are concrete test gaps — write tests that kill them.
