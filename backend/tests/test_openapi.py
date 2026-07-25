"""Guards on the generated OpenAPI document."""

from collections import Counter
from typing import Any

from src.main import app

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _operations() -> list[tuple[str, str, dict[str, Any]]]:
    """Every (path, method, operation) in the schema, ignoring path-level keys."""
    schema = app.openapi()
    return [
        (path, method, operation)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def test_operation_ids_are_unique() -> None:
    """
    Handler names are the operationIds, so a duplicate name anywhere in the app
    would merge two operations into one and silently drop it from generated
    clients. Rename one of the handlers rather than relaxing this.
    """
    counts = Counter(operation["operationId"] for _, _, operation in _operations())
    duplicates = {name: count for name, count in counts.items() if count > 1}

    assert not duplicates, (
        f"Duplicate operationIds: {duplicates}. Handler names must be unique across "
        "every router, because src.infrastructure.common.openapi.operation_id uses "
        "the handler name as the operationId."
    )


def test_operation_ids_are_bare_handler_names() -> None:
    """
    Catches a silent revert to FastAPI's default scheme, which appends the path
    and method and produces the long names generated clients used to carry.
    """
    offenders = [
        (path, method, operation["operationId"])
        for path, method, operation in _operations()
        if operation["operationId"].endswith(f"_{method}")
    ]

    assert not offenders, (
        f"operationIds look path-and-method derived: {offenders}. Check that "
        "generate_unique_id_function is still wired into the FastAPI app."
    )
