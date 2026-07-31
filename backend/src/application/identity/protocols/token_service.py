"""Protocol for token service."""

from datetime import datetime
from typing import Protocol

from src.application.identity.dtos import RefreshTokenClaims, TokenPairWithMetadata


class TokenServiceProtocol(Protocol):
    def create_token_pair(self, user_id: int, family_id: str) -> TokenPairWithMetadata: ...

    def reissue_token_pair(
        self, user_id: int, family_id: str, jti: str, refresh_token_expires_at: datetime
    ) -> TokenPairWithMetadata: ...

    def verify_refresh_token(self, token: str) -> RefreshTokenClaims | None: ...
