"""Client-version gate for the endpoints only our own clients call.

Clients identify themselves with ``X-Crossbill-Client: <name>/<x.y.z>``, and a
client older than the deployed server needs gets 426 Upgrade Required with a
body naming the minimum. A missing header counts as too old, because plugins
predating the gate send none. A client we have no requirement for passes
through: this gates our own clients' versions, not who may call the API.
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


# The minimum says what *this* server needs a client to be able to do, so bump
# it in the same PR as any change that breaks the gated contract for older
# clients -- never on its own, and never without one.
CLIENT_VERSION_REQUIREMENTS: Final[Mapping[str, ClientVersionRequirement]] = {
    KOREADER_PLUGIN: ClientVersionRequirement(
        min_version=(0, 12, 0),
        update_url="https://github.com/Crossbill-App/koreader-plugin",
    ),
}

# Strictly three plain numeric parts, no pre-release or build suffixes. Segment
# length is bounded so ``int()`` can never raise on regex-validated input --
# this runs before authentication.
_VERSION_PATTERN: Final = re.compile(r"[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}")


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

    The expected client is named per surface so the 426 body can say which
    client to upgrade even when the request names none.
    """
    expected_requirement = CLIENT_VERSION_REQUIREMENTS[expected_client]

    async def dependency(
        client_header: Annotated[str | None, Header(alias=CLIENT_VERSION_HEADER)] = None,
    ) -> None:
        # An empty value names no client, so it must not pass as an unknown one.
        announced = "" if client_header is None else client_header.strip()
        if not announced:
            _upgrade_required(expected_client, expected_requirement, received_version=None)

        name, _, raw_version = announced.partition("/")
        requirement = CLIENT_VERSION_REQUIREMENTS.get(name)
        if requirement is None:
            return

        version = _parse_version(raw_version)
        if version is None:
            # Fail closed: an unreadable version is no evidence of a new enough client.
            _upgrade_required(name, requirement, received_version=None)

        if version < requirement.min_version:
            _upgrade_required(name, requirement, received_version=raw_version)

    return dependency


require_koreader_plugin: Final = require_client_version(KOREADER_PLUGIN)

# Shared OpenAPI metadata: 426 is unique to this gate across the API, so the
# status code alone identifies the failure.
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
