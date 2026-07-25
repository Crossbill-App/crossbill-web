"""OpenAPI operation id generation."""

from fastapi.routing import APIRoute


def operation_id(route: APIRoute) -> str:
    """
    Use the route handler's own name as its OpenAPI operationId.

    FastAPI's default appends the path and method to the handler name, so
    `update_tag` becomes `update_tag_api_v1_books__book_id__tag__tag_id__post`.
    Generated clients carry that through: orval turns it into the 42-character
    `useUpdateTagApiV1BooksBookIdTagTagIdPost`, and those names reach ordinary
    components. The handler name on its own already says what the operation is,
    and the path is one field away in the same document.

    This makes handler names an API-visible contract: two handlers sharing a
    name anywhere in the app would collide into one operationId and silently
    drop an operation from generated clients. `tests/test_openapi.py` asserts
    they stay unique.
    """
    return route.name
