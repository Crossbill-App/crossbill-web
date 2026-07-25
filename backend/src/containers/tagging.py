from dependency_injector import containers, providers

from src.application.tagging.use_cases.tag_groups.create_tag_group_use_case import (
    CreateTagGroupUseCase,
)
from src.application.tagging.use_cases.tag_groups.delete_tag_group_use_case import (
    DeleteTagGroupUseCase,
)
from src.application.tagging.use_cases.tag_groups.update_tag_group_association_use_case import (
    UpdateTagGroupAssociationUseCase,
)
from src.application.tagging.use_cases.tag_groups.update_tag_group_use_case import (
    UpdateTagGroupUseCase,
)
from src.application.tagging.use_cases.tags.create_tag_use_case import (
    CreateTagUseCase,
)
from src.application.tagging.use_cases.tags.delete_tag_use_case import (
    DeleteTagUseCase,
)
from src.application.tagging.use_cases.tags.get_tags_for_book_use_case import (
    GetTagsForBookUseCase,
)
from src.application.tagging.use_cases.tags.update_tag_name_use_case import (
    UpdateTagNameUseCase,
)


class TaggingContainer(containers.DeclarativeContainer):
    """Tagging module use cases."""

    # Dependencies from shared
    tag_repository = providers.Dependency()
    book_repository = providers.Dependency()

    # Tags
    create_tag_use_case = providers.Factory(
        CreateTagUseCase,
        tag_repository=tag_repository,
        book_repository=book_repository,
    )
    delete_tag_use_case = providers.Factory(
        DeleteTagUseCase,
        tag_repository=tag_repository,
    )
    update_tag_name_use_case = providers.Factory(
        UpdateTagNameUseCase,
        tag_repository=tag_repository,
    )
    get_tags_for_book_use_case = providers.Factory(
        GetTagsForBookUseCase,
        tag_repository=tag_repository,
        book_repository=book_repository,
    )

    # Tag groups
    create_tag_group_use_case = providers.Factory(
        CreateTagGroupUseCase,
        tag_repository=tag_repository,
        book_repository=book_repository,
    )
    update_tag_group_use_case = providers.Factory(
        UpdateTagGroupUseCase,
        tag_repository=tag_repository,
        book_repository=book_repository,
    )
    delete_tag_group_use_case = providers.Factory(
        DeleteTagGroupUseCase,
        tag_repository=tag_repository,
    )
    update_tag_group_association_use_case = providers.Factory(
        UpdateTagGroupAssociationUseCase,
        tag_repository=tag_repository,
    )
