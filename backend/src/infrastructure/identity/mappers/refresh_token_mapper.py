"""Mapper for RefreshToken ORM <-> Domain conversion."""

from datetime import UTC, datetime

from src.domain.common.value_objects.ids import RefreshTokenId, UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.identity.orm.refresh_token_model import RefreshToken as RefreshTokenORM


def _as_utc(value: datetime) -> datetime:
    """Restore the tzinfo SQLite drops.

    These columns are ``DateTime(timezone=True)`` and always hold UTC, but
    SQLite has no timezone type and hands the value back naive. The entity
    compares them against ``datetime.now(UTC)``, which raises on a naive
    operand, so the offset is put back at the boundary rather than defended
    against in the domain.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _as_utc(value)


class RefreshTokenMapper:
    """Mapper for RefreshToken ORM <-> Domain conversion."""

    def to_domain(self, orm_model: RefreshTokenORM) -> RefreshToken:
        return RefreshToken.create_with_id(
            id=RefreshTokenId(orm_model.id),
            jti=orm_model.jti,
            user_id=UserId(orm_model.user_id),
            family_id=orm_model.family_id,
            revoked_at=_as_utc_or_none(orm_model.revoked_at),
            expires_at=_as_utc(orm_model.expires_at),
            created_at=_as_utc(orm_model.created_at),
            replaced_by_jti=orm_model.replaced_by_jti,
        )

    def to_orm(self, domain_entity: RefreshToken) -> RefreshTokenORM:
        return RefreshTokenORM(
            id=orm_id(domain_entity.id),
            jti=domain_entity.jti,
            user_id=domain_entity.user_id.value,
            family_id=domain_entity.family_id,
            revoked_at=domain_entity.revoked_at,
            expires_at=domain_entity.expires_at,
            replaced_by_jti=domain_entity.replaced_by_jti,
        )
