"""
Pydantic schemas for request/response validation.

Covers:
- Chat API request/response
- Answer submission request/response
- Candidate profile
- Conversation state
- Health check
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Conversation FSM stages ───────────────────────────────────────────────────

class ConversationStage(str, Enum):
    """States in the hiring chatbot finite state machine."""

    GREETING = "greeting"
    COLLECT_NAME = "collect_name"
    COLLECT_EMAIL = "collect_email"
    COLLECT_PHONE = "collect_phone"
    COLLECT_EXPERIENCE = "collect_experience"
    COLLECT_ROLE = "collect_role"
    COLLECT_LOCATION = "collect_location"
    COLLECT_TECH_STACK = "collect_tech_stack"
    GENERATE_QUESTIONS = "generate_questions"   # kept for legacy sessions in DB
    ANSWERING_QUESTIONS = "answering_questions"  # dedicated Q&A form stage
    ENDED = "ended"


# ── Message ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


# ── Chat API ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming chat request from frontend."""

    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str | None = Field(
        default=None,
        description="UUID of an existing session. Omit to start a new session.",
    )


class QuestionItem(BaseModel):
    """A single generated technical question, as returned to the frontend."""

    id: int
    technology: str
    question_text: str


class ChatResponse(BaseModel):
    """Outgoing chat response to frontend."""

    session_id: str
    message: str
    stage: ConversationStage
    is_ended: bool = False
    questions: list[QuestionItem] | None = None  # populated only at ANSWERING_QUESTIONS stage


# ── Answer submission ─────────────────────────────────────────────────────────

class AnswerItem(BaseModel):
    """A single question-answer pair submitted by the candidate."""

    question_id: int
    answer: str = Field(..., min_length=1, description="Answer cannot be blank.")


class SubmitAnswersRequest(BaseModel):
    """Request body for POST /answers."""

    session_id: str
    answers: list[AnswerItem] = Field(..., min_length=1)


# ── Candidate ─────────────────────────────────────────────────────────────────

class CandidateCreate(BaseModel):
    """Data required to create a Candidate record."""

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    experience: str | None = None
    desired_role: str | None = None
    location: str | None = None
    tech_stack: list[str] = Field(default_factory=list)

    @field_validator("tech_stack", mode="before")
    @classmethod
    def parse_tech_stack(cls, v: Any) -> list[str]:
        """Accept a comma-separated string or a list."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v or []


class CandidateRead(CandidateCreate):
    """Candidate record as returned from the DB."""

    id: int

    model_config = {"from_attributes": True}


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response from GET /health."""

    status: str = "ok"
    app: str
    version: str
