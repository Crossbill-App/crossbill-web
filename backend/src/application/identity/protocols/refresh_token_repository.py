"""Protocol for refresh token repository."""

from typing import Protocol

from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.refresh_token import RefreshToken


class RefreshTokenRepositoryProtocol(Protocol):
    async def find_by_jti(self, jti: str) -> RefreshToken | None: ...

    async def save(self, token: RefreshToken) -> RefreshToken: ...

    async def revoke(self, token: RefreshToken) -> None: ...

    async def revoke_family(self, family_id: str) -> None: ...

    async def revoke_all_for_user(
        self, user_id: UserId, except_family_id: str | None = None
    ) -> None: ...

    async def delete_expired_for_user(self, user_id: UserId) -> None: ...
