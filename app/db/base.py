"""
SQLAlchemy declarative base.

All ORM models must import Base from this module so that
`Base.metadata.create_all()` picks them up automatically.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


# Re-export for convenience ──────────────────────────────────────────────────
__all__ = ["Base"]
