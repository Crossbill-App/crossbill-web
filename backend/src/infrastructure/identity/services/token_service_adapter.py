"""Adapter wrapping token service functions for DI."""

from datetime import datetime

from src.application.identity.dtos import RefreshTokenClaims, TokenPairWithMetadata
from src.infrastructure.identity.services import token_service


class TokenServiceAdapter:
    """Adapter wrapping token service functions for DI."""

    def create_token_pair(self, user_id: int, family_id: str) -> TokenPairWithMetadata:
        return token_service.create_token_pair(user_id, family_id)

    def reissue_token_pair(
        self, user_id: int, family_id: str, jti: str, refresh_token_expires_at: datetime
    ) -> TokenPairWithMetadata:
        return token_service.reissue_token_pair(user_id, family_id, jti, refresh_token_expires_at)

    def verify_refresh_token(self, token: str) -> RefreshTokenClaims | None:
        return token_service.verify_refresh_token(token)
