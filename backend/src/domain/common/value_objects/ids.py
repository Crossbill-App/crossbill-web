from dataclasses import dataclass

from ..entity import EntityId


@dataclass(frozen=True)
class BookId(EntityId):
    """Strongly-typed book identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("BookId must be non-negative")


@dataclass(frozen=True)
class UserId(EntityId):
    """Strongly-typed user identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("UserId must be non-negative")


@dataclass(frozen=True)
class HighlightId(EntityId):
    """Strongly-typed highlight identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("HighlightId must be non-negative")


@dataclass(frozen=True)
class HighlightStyleId(EntityId):
    """Strongly-typed highlight style identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("HighlightStyleId must be non-negative")

    @classmethod
    def generate(cls) -> "HighlightStyleId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class ChapterId(EntityId):
    """Strongly-typed chapter identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("ChapterId must be non-negative")


@dataclass(frozen=True)
class ReadingSessionId(EntityId):
    """Strongly-typed reading session identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("ReadingSessionId must be non-negative")


@dataclass(frozen=True)
class TagId(EntityId):
    """Strongly-typed tag identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("TagId must be non-negative")

    @classmethod
    def generate(cls) -> "TagId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class TagGroupId(EntityId):
    """Strongly-typed tag group identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("TagGroupId must be non-negative")

    @classmethod
    def generate(cls) -> "TagGroupId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class FlashcardId(EntityId):
    """Strongly-typed flashcard identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("FlashcardId must be non-negative")

    @classmethod
    def generate(cls) -> "FlashcardId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class NoteId(EntityId):
    """Strongly-typed note identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("NoteId must be non-negative")

    @classmethod
    def generate(cls) -> "NoteId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class BookReflectionId(EntityId):
    """Strongly-typed book reflection identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("BookReflectionId must be non-negative")

    @classmethod
    def generate(cls) -> "BookReflectionId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class BookmarkId(EntityId):
    """Strongly-typed bookmark identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("BookmarkId must be non-negative")

    @classmethod
    def generate(cls) -> "BookmarkId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class ChapterDigestId(EntityId):
    """Strongly-typed chapter digest identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("ChapterDigestId must be non-negative")

    @classmethod
    def generate(cls) -> "ChapterDigestId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class AIUsageRecordId(EntityId):
    """Strongly-typed AI usage record identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("AIUsageRecordId must be non-negative")

    @classmethod
    def generate(cls) -> "AIUsageRecordId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class AIChatSessionId(EntityId):
    """Strongly-typed AI chat session identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("AIChatSessionId must be non-negative")

    @classmethod
    def generate(cls) -> "AIChatSessionId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class RefreshTokenId(EntityId):
    """Strongly-typed refresh token identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("RefreshTokenId must be non-negative")

    @classmethod
    def generate(cls) -> "RefreshTokenId":
        return cls(0)  # Database assigns real ID


@dataclass(frozen=True)
class JobBatchId(EntityId):
    """Strongly-typed job batch identifier."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("JobBatchId must be non-negative")

    @classmethod
    def generate(cls) -> "JobBatchId":
        return cls(0)  # Database assigns real ID
