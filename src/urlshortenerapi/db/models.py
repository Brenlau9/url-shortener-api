from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    BigInteger,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from urlshortenerapi.db.base import Base


class Link(Base):
    __tablename__ = "links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        index=True,
    )

    long_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    max_clicks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="NULL or 0 means unlimited",
    )

    click_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )

    last_accessed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Store ONLY a hash of the API key (never plaintext)
    key_hash: Mapped[str] = mapped_column(
        String(64),  # sha256 hex digest length
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="default",
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
