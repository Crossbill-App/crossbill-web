"""Client-version gate for the endpoints only our own clients call.

The KOReader plugin identifies itself with ``X-Crossbill-Client:
koreader-plugin/<x.y.z>`` on every request. The endpoints that exist solely for
that plugin refuse anything older than the deployed server needs, answering 426
Upgrade Required, so a stale plugin fails at the door with an actionable body
instead of half-working further in.

A missing header is treated as too old on purpose: every plugin released before
this gate sends nothing at all, so absence *is* the signal that the caller
predates the version we require. Callers naming a client we know nothing about
pass through -- this gate polices the versions of our own clients, not who may
call the API; authentication does that.
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Final, NoReturn

from fastapi import Header, HTTPException, status

CLIENT_VERSION_HEADER: Final = "X-Crossbill-Client"

KOREADER_PLUGIN: Final = "koreader-plugin"

UPGRADE_REQUIRED_CODE: Final = "client_upgrade_required"


@dataclass(frozen=True)
class ClientVersionRequirement:
    """What one first-party client has to be for this server to serve it."""

    min_version: tuple[int, int, int]
    update_url: str


# The minimum is a property of the deployed code, not a policy dial: it says
# what *this* server needs a client to be able to do. Bump it in the same PR as
# any change that breaks the request or response contract of the gated surface
# for older clients, never out of band -- a bump on its own locks out clients
# the running code could still serve, and a breaking change without one leaves
# clients that the new code cannot serve to fail somewhere deeper and vaguer.
CLIENT_VERSION_REQUIREMENTS: Final[Mapping[str, ClientVersionRequirement]] = {
    KOREADER_PLUGIN: ClientVersionRequirement(
        min_version=(0, 13, 0),
        update_url="https://github.com/Crossbill-App/koreader-plugin",
    ),
}

# Strict ``name/major.minor.patch``. No pre-release or build suffixes: our
# clients ship plain three-part versions, and anything else is a client we
# cannot reason about rather than one to guess at.
_VERSION_PATTERN: Final = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def format_version(version: tuple[int, int, int]) -> str:
    """Render a version tuple the way clients write it."""
    return ".".join(str(part) for part in version)


def _parse_version(raw: str) -> tuple[int, int, int] | None:
    """Parse ``major.minor.patch`` into a tuple, or ``None`` if it is not that."""
    if _VERSION_PATTERN.fullmatch(raw) is None:
        return None
    major, minor, patch = (int(part) for part in raw.split("."))
    return (major, minor, patch)


def _upgrade_required(
    client: str,
    requirement: ClientVersionRequirement,
    received_version: str | None,
) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_426_UPGRADE_REQUIRED,
        detail={
            "code": UPGRADE_REQUIRED_CODE,
            "client": client,
            "min_supported_version": format_version(requirement.min_version),
            "received_version": received_version,
            "update_url": requirement.update_url,
        },
    )


def require_client_version(expected_client: str) -> Callable[[str | None], Awaitable[None]]:
    """Build the dependency guarding a surface that only ``expected_client`` calls.

    The expected client is named per surface because a request without the
    header names no client at all, and the 426 body still has to say which
    client to upgrade and where to get it.
    """
    expected_requirement = CLIENT_VERSION_REQUIREMENTS[expected_client]

    async def dependency(
        client_header: Annotated[str | None, Header(alias=CLIENT_VERSION_HEADER)] = None,
    ) -> None:
        if client_header is None:
            _upgrade_required(expected_client, expected_requirement, received_version=None)

        name, _, raw_version = client_header.strip().partition("/")
        requirement = CLIENT_VERSION_REQUIREMENTS.get(name)
        if requirement is None:
            return

        version = _parse_version(raw_version)
        if version is None:
            # Fail closed: a client of ours whose version we cannot read is not
            # a client we can claim meets the minimum.
            _upgrade_required(name, requirement, received_version=None)

        if version < requirement.min_version:
            _upgrade_required(name, requirement, received_version=raw_version)

    return dependency


require_koreader_plugin: Final = require_client_version(KOREADER_PLUGIN)

# Shared OpenAPI metadata for the gated endpoints. 426 is unique to this gate
# across the API, so the status code alone identifies the failure.
UPGRADE_REQUIRED_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    status.HTTP_426_UPGRADE_REQUIRED: {
        "description": (
            "The caller is an outdated Crossbill client, or sent no "
            f"{CLIENT_VERSION_HEADER} header at all. The body names the minimum "
            "supported version and where to get it."
        ),
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": UPGRADE_REQUIRED_CODE,
                        "client": KOREADER_PLUGIN,
                        "min_supported_version": format_version(
                            CLIENT_VERSION_REQUIREMENTS[KOREADER_PLUGIN].min_version
                        ),
                        "received_version": "0.12.0",
                        "update_url": CLIENT_VERSION_REQUIREMENTS[KOREADER_PLUGIN].update_url,
                    }
                }
            }
        },
    }
}
