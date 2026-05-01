"""
ORM models for Candidate, CandidateTechStack, TechnicalQuestion, and Conversation.

Tables:
  candidates           — collected candidate profile data
  candidate_tech_stack — one row per declared technology per candidate
  technical_questions  — one row per generated question; stores the answer after submission
  conversations        — full message history and current chat FSM stage
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Candidate(Base):
    """Stores structured profile data collected during the interview chat."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    desired_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Denormalised JSONB copy kept for backward-compat / quick reads
    tech_stack: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="candidate", cascade="all, delete-orphan",
    )
    tech_stack_entries: Mapped[list["CandidateTechStack"]] = relationship(
        "CandidateTechStack", back_populates="candidate", cascade="all, delete-orphan",
    )
    technical_questions: Mapped[list["TechnicalQuestion"]] = relationship(
        "TechnicalQuestion", back_populates="candidate", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name!r} email={self.email!r}>"


class CandidateTechStack(Base):
    """
    Normalised tech-stack table — one row per technology declared by a candidate.

    Example rows for a candidate who listed "Python, Django, PostgreSQL":
        (candidate_id=5, technology="Python")
        (candidate_id=5, technology="Django")
        (candidate_id=5, technology="PostgreSQL")
    """

    __tablename__ = "candidate_tech_stack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technology: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="tech_stack_entries")
    questions: Mapped[list["TechnicalQuestion"]] = relationship(
        "TechnicalQuestion", back_populates="tech_stack_entry", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CandidateTechStack id={self.id} tech={self.technology!r} candidate={self.candidate_id}>"


class TechnicalQuestion(Base):
    """
    One row per generated technical interview question.

    `answer` starts as NULL and is populated when the candidate submits
    answers via POST /api/v1/answers.
    """

    __tablename__ = "technical_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tech_stack_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_tech_stack.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="technical_questions")
    tech_stack_entry: Mapped["CandidateTechStack"] = relationship(
        "CandidateTechStack", back_populates="questions",
    )

    def __repr__(self) -> str:
        return (
            f"<TechnicalQuestion id={self.id} "
            f"tech_stack_id={self.tech_stack_id} "
            f"answered={'yes' if self.answer else 'no'}>"
        )


class Conversation(Base):
    """
    Tracks a single chat session for a candidate.

    `messages` is a JSON array of message dicts:
        [{"role": "assistant"|"user", "content": "..."}, ...]

    `current_stage` is a string representing the current FSM stage.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="greeting")
    collected_info: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    candidate: Mapped["Candidate | None"] = relationship("Candidate", back_populates="conversations")

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id!r} stage={self.current_stage!r} "
            f"candidate_id={self.candidate_id}>"
        )
