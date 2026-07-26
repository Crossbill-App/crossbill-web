"""
Use case for deleting a tag group.
"""

import structlog

from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import TagGroupId

logger = structlog.get_logger(__name__)


class DeleteTagGroupUseCase:
    """Use case for deleting a tag group."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository

    async def delete_group(self, group_id: int, user_id: int) -> bool:
        """
        Delete a tag group (nullifies tag associations).

        Args:
            group_id: ID of the group to delete
            user_id: ID of the user

        Returns:
            True if deleted, False if not found
        """
        group_id_vo = TagGroupId(group_id)

        success = await self.tag_repository.delete_group(group_id_vo)
        if success:
            logger.info("deleted_tag_group", group_id=group_id)

        return success
