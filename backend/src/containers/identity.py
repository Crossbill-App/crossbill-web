from dependency_injector import containers, providers

from src.application.identity.use_cases.authentication.authenticate_user_use_case import (
    AuthenticateUserUseCase,
)
from src.application.identity.use_cases.authentication.get_user_by_id_use_case import (
    GetUserByIdUseCase,
)
from src.application.identity.use_cases.authentication.logout_use_case import LogoutUseCase
from src.application.identity.use_cases.authentication.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.application.identity.use_cases.register_user_use_case import RegisterUserUseCase
from src.application.identity.use_cases.update_user_use_case import UpdateUserUseCase


class IdentityContainer(containers.DeclarativeContainer):
    """Identity module use cases."""

    user_repository = providers.Dependency()
    password_service = providers.Dependency()
    token_service = providers.Dependency()
    refresh_token_repository = providers.Dependency()

    authenticate_user_use_case = providers.Factory(
        AuthenticateUserUseCase,
        user_repository=user_repository,
        password_service=password_service,
        token_service=token_service,
        refresh_token_repository=refresh_token_repository,
    )
    refresh_access_token_use_case = providers.Factory(
        RefreshAccessTokenUseCase,
        user_repository=user_repository,
        token_service=token_service,
        refresh_token_repository=refresh_token_repository,
    )
    get_user_by_id_use_case = providers.Factory(
        GetUserByIdUseCase,
        user_repository=user_repository,
    )
    register_user_use_case = providers.Factory(
        RegisterUserUseCase,
        user_repository=user_repository,
        password_service=password_service,
        token_service=token_service,
        refresh_token_repository=refresh_token_repository,
    )
    update_user_use_case = providers.Factory(
        UpdateUserUseCase,
        user_repository=user_repository,
        password_service=password_service,
        token_service=token_service,
        refresh_token_repository=refresh_token_repository,
    )
    logout_use_case = providers.Factory(
        LogoutUseCase,
        token_service=token_service,
        refresh_token_repository=refresh_token_repository,
    )
