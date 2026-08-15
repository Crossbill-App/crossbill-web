"""Server-enforced user confirmation for destructive MCP tools."""

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.types import ClientCapabilities, ElicitationCapability
from pydantic import BaseModel, Field

NO_ELICITATION_MESSAGE = (
    "Deletion not performed: this client does not support confirmation "
    "prompts (MCP elicitation). Delete this from the Crossbill web UI "
    "instead."
)

CANCELLED_MESSAGE = "Deletion cancelled by user."

REQUIRES_USER_INTERACTION = {"anthropic/requiresUserInteraction": True}


class DeletionConfirmation(BaseModel):
    """The single yes/no field the user answers before a deletion runs."""

    confirm: bool = Field(
        default=False,
        title="Delete permanently",
        description="Tick to confirm this deletion. Leave unticked to cancel.",
    )


async def block_unconfirmed_deletion(
    ctx: Context[ServerSession, None], message: str
) -> str | None:
    """Ask the user to confirm a deletion before it happens.

    Returns None when the user explicitly confirmed and the caller may go
    ahead. Otherwise returns the message the tool should hand back instead of
    deleting anything: clients that never declared the elicitation capability
    cannot be asked at all, so their deletions are refused outright.
    """
    supports_elicitation = ctx.session.check_client_capability(
        ClientCapabilities(elicitation=ElicitationCapability())
    )
    if not supports_elicitation:
        return NO_ELICITATION_MESSAGE

    result = await ctx.elicit(message=message, schema=DeletionConfirmation)
    if result.action == "accept" and result.data.confirm:
        return None
    return CANCELLED_MESSAGE
