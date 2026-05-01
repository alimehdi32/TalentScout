"""
API route definitions.

All routes are collected in a single APIRouter and mounted by main.py.

Endpoints:
  POST /chat     — main chatbot endpoint
  POST /answers  — submit candidate answers for generated questions
  GET  /health   — readiness probe
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.candidate import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    QuestionItem,
    SubmitAnswersRequest,
)
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Health check ──────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health probe",
    tags=["infra"],
)
def health() -> HealthResponse:
    """Return a 200 OK with basic service metadata."""
    return HealthResponse(app=settings.APP_NAME, version=settings.APP_VERSION)


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to TalentScout",
    tags=["chat"],
    status_code=status.HTTP_200_OK,
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Process a user message through the hiring chatbot FSM.

    - If `session_id` is omitted a new session is created.
    - When the stage transitions to ANSWERING_QUESTIONS, the response includes
      a `questions` list for the frontend to render the answer form.
    """
    try:
        reply, session_id, stage, is_ended, questions = chat_service.process_message(
            db=db,
            user_message=request.message,
            session_id=request.session_id,
        )
    except Exception as exc:
        logger.exception("Unhandled error in /chat: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again.",
        ) from exc

    return ChatResponse(
        session_id=session_id,
        message=reply,
        stage=stage,
        is_ended=is_ended,
        questions=questions,
    )


# ── Answer submission endpoint ────────────────────────────────────────────────

@router.post(
    "/answers",
    response_model=ChatResponse,
    summary="Submit answers to generated technical questions",
    tags=["chat"],
    status_code=status.HTTP_200_OK,
)
def submit_answers(
    request: SubmitAnswersRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Accept the candidate's answers for all generated technical questions.

    - All question IDs must belong to the session's candidate.
    - All answers must be non-blank (422 returned otherwise).
    - On success the session is transitioned to ENDED.
    """
    answers_payload = [
        {"question_id": a.question_id, "answer": a.answer}
        for a in request.answers
    ]

    try:
        reply, stage = chat_service.submit_answers(
            db=db,
            session_id=request.session_id,
            answers=answers_payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /answers: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while saving your answers. Please try again.",
        ) from exc

    return ChatResponse(
        session_id=request.session_id,
        message=reply,
        stage=stage,
        is_ended=True,
    )
