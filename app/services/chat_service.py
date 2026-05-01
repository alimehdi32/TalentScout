"""
Chat Service — Conversational State Machine (FSM).

Orchestrates the full hiring interview flow:

  GREETING → COLLECT_NAME → COLLECT_EMAIL → COLLECT_PHONE
           → COLLECT_EXPERIENCE → COLLECT_ROLE → COLLECT_LOCATION
           → COLLECT_TECH_STACK  (questions generated immediately here)
           → ANSWERING_QUESTIONS (candidate fills form; answers submitted via POST /answers)
           → ENDED

Each stage has:
  - An entry message (what the bot says when entering the stage)
  - A handler (processes user input and advances to the next stage)

The service is stateless; all state lives in the `conversations` DB table.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateTechStack, Conversation, TechnicalQuestion
from app.schemas.candidate import ConversationStage, QuestionItem
from app.services import llm_service

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

EXIT_KEYWORDS = frozenset({"exit", "quit", "bye", "goodbye", "stop", "end"})

_STAGE_PROMPTS: dict[ConversationStage, str] = {
    ConversationStage.GREETING: (
        "Hello! I'm **TalentScout**, an AI-powered hiring assistant for TalentScout Recruitment Agency.\n\n"
        "My purpose is to conduct your initial screening interview. I'll collect some basic profile "
        "details and then generate a set of technical questions tailored specifically to your declared "
        "tech stack — helping us match you with the right opportunities.\n\n"
        "The conversation is confidential and your data is handled securely. "
        "You can type **exit** or **bye** at any time to end the session.\n\n"
        "Let's get started! Could you please tell me your **full name**?"
    ),
    ConversationStage.COLLECT_NAME: "What is your **full name**?",
    ConversationStage.COLLECT_EMAIL: "Thanks, {name}! What is your **email address**?",
    ConversationStage.COLLECT_PHONE: "What is your **phone number**?",
    ConversationStage.COLLECT_EXPERIENCE: (
        "How many **years of professional experience** do you have?"
    ),
    ConversationStage.COLLECT_ROLE: "What **position(s)** are you looking for?",
    ConversationStage.COLLECT_LOCATION: "What is your **current location** (or preferred work location)?",
    ConversationStage.COLLECT_TECH_STACK: (
        "Please list your **tech stack** — the programming languages, frameworks, databases, "
        "and tools you are proficient in (e.g., Python, React, PostgreSQL, Docker)."
    ),
    ConversationStage.GENERATE_QUESTIONS: "",   # legacy — no longer reached in normal flow
    ConversationStage.ANSWERING_QUESTIONS: (
        "Your questions are ready. Please answer all questions in the form below."
    ),
    ConversationStage.ENDED: (
        "Thank you for completing your TalentScout screening interview, {name}!\n\n"
        "**What happens next?**\n"
        "- Our recruitment team will review your profile and technical responses.\n"
        "- If your profile matches any open roles, a TalentScout recruiter will reach out "
        "to you at the contact details you provided within 3–5 business days.\n"
        "- We appreciate your time and wish you the best of luck!\n\n"
        "Feel free to type **bye** to close this session."
    ),
}

# Ordered FSM transition map
_NEXT_STAGE: dict[ConversationStage, ConversationStage] = {
    ConversationStage.GREETING: ConversationStage.COLLECT_NAME,
    ConversationStage.COLLECT_NAME: ConversationStage.COLLECT_EMAIL,
    ConversationStage.COLLECT_EMAIL: ConversationStage.COLLECT_PHONE,
    ConversationStage.COLLECT_PHONE: ConversationStage.COLLECT_EXPERIENCE,
    ConversationStage.COLLECT_EXPERIENCE: ConversationStage.COLLECT_ROLE,
    ConversationStage.COLLECT_ROLE: ConversationStage.COLLECT_LOCATION,
    ConversationStage.COLLECT_LOCATION: ConversationStage.COLLECT_TECH_STACK,
    ConversationStage.COLLECT_TECH_STACK: ConversationStage.ANSWERING_QUESTIONS,
    ConversationStage.GENERATE_QUESTIONS: ConversationStage.ANSWERING_QUESTIONS,  # legacy
    ConversationStage.ANSWERING_QUESTIONS: ConversationStage.ENDED,
    ConversationStage.ENDED: ConversationStage.ENDED,
}


# ── Helper utilities ──────────────────────────────────────────────────────────

def _is_exit(text: str) -> bool:
    """Return True if the user's message is an exit signal."""
    return text.strip().lower() in EXIT_KEYWORDS


def _is_blank(text: str) -> bool:
    """Return True when the input is empty, too short, or clearly non-informative."""
    stripped = text.strip()
    if not stripped:
        return True
    # Single-character inputs (except digits like "5" for experience) are likely garbage
    if len(stripped) <= 1 and not stripped.isdigit():
        return True
    return False


def _format_prompt(stage: ConversationStage, info: dict[str, Any]) -> str:
    """Return the bot's entry message for *stage*, interpolating collected info."""
    template = _STAGE_PROMPTS.get(stage, "")
    try:
        return template.format(**info)
    except KeyError:
        return template


def _append_message(conv: Conversation, role: str, content: str) -> None:
    """Append a message dict to conv.messages (JSONB list)."""
    messages: list[dict[str, str]] = list(conv.messages or [])
    messages.append({"role": role, "content": content})
    conv.messages = messages  # type: ignore[assignment]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_or_create_conversation(db: Session, session_id: str | None) -> Conversation:
    """
    Load an existing Conversation by session_id, or create a brand-new one.
    A new session always starts at the GREETING stage.
    """
    if session_id:
        conv = db.get(Conversation, session_id)
        if conv:
            return conv
        logger.warning("Session %r not found — starting fresh.", session_id)

    conv = Conversation(
        id=str(uuid.uuid4()),
        messages=[],
        current_stage=ConversationStage.GREETING.value,
        collected_info={},
    )
    db.add(conv)
    db.flush()
    return conv


def _persist_candidate(db: Session, conv: Conversation) -> None:
    """
    Upsert candidate info into the `candidates` table and link to conversation.
    If a candidate with the same email already exists, their record is updated.
    """
    info: dict[str, Any] = conv.collected_info or {}
    if not info:
        return

    email = info.get("email")
    candidate: Candidate | None = None

    if email:
        candidate = db.query(Candidate).filter(Candidate.email == email).first()

    if candidate:
        candidate.name = info.get("name") or candidate.name
        candidate.phone = info.get("phone") or candidate.phone
        candidate.experience = info.get("experience") or candidate.experience
        candidate.desired_role = info.get("desired_role") or candidate.desired_role
        candidate.location = info.get("location") or candidate.location
        candidate.tech_stack = info.get("tech_stack") or candidate.tech_stack
        logger.info("Updated existing candidate id=%s (email=%r)", candidate.id, email)
    else:
        candidate = Candidate(
            name=info.get("name"),
            email=email,
            phone=info.get("phone"),
            experience=info.get("experience"),
            desired_role=info.get("desired_role"),
            location=info.get("location"),
            tech_stack=info.get("tech_stack", []),
        )
        db.add(candidate)
        db.flush()
        logger.info("Created new candidate id=%s (email=%r)", candidate.id, email)

    conv.candidate_id = candidate.id


def _persist_tech_stack_and_questions(
    db: Session,
    conv: Conversation,
    raw_questions: list[dict[str, str]],
) -> list[QuestionItem]:
    """
    Persist tech stack entries and generated questions to the DB.

    For each unique technology in `raw_questions`, inserts one row into
    `candidate_tech_stack`. For each question, inserts one row into
    `technical_questions` linked to both the candidate and the tech stack entry.

    Returns a list of QuestionItem dicts ready to send to the frontend.
    """
    if not conv.candidate_id or not raw_questions:
        return []

    # Map technology name → CandidateTechStack row (avoid duplicates)
    tech_map: dict[str, CandidateTechStack] = {}
    saved: list[QuestionItem] = []

    for item in raw_questions:
        tech = item.get("technology", "").strip()
        question_text = item.get("question", "").strip()

        if not tech or not question_text:
            logger.debug("Skipping malformed question item: %r", item)
            continue

        # Create tech stack entry if first time seeing this technology
        if tech not in tech_map:
            ts_entry = CandidateTechStack(
                candidate_id=conv.candidate_id,
                technology=tech,
            )
            db.add(ts_entry)
            db.flush()  # get auto-generated id
            tech_map[tech] = ts_entry
            logger.debug("Created CandidateTechStack id=%s tech=%r", ts_entry.id, tech)

        tq = TechnicalQuestion(
            candidate_id=conv.candidate_id,
            tech_stack_id=tech_map[tech].id,
            question_text=question_text,
        )
        db.add(tq)
        db.flush()  # get auto-generated id
        saved.append(QuestionItem(id=tq.id, technology=tech, question_text=question_text))

    logger.info(
        "Persisted %d questions across %d technologies for candidate id=%s",
        len(saved), len(tech_map), conv.candidate_id,
    )
    return saved


# ── FSM stage handlers ────────────────────────────────────────────────────────

def _handle_greeting(conv: Conversation, _user_msg: str) -> str:
    """Transition from GREETING → COLLECT_NAME and emit greeting."""
    conv.current_stage = ConversationStage.COLLECT_NAME.value
    return _format_prompt(ConversationStage.GREETING, conv.collected_info)


def _handle_collect_name(conv: Conversation, user_msg: str) -> str:
    if _is_blank(user_msg):
        return "I didn't catch that. Could you please tell me your **full name**?"
    info: dict[str, Any] = dict(conv.collected_info)
    info["name"] = user_msg.strip()
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_NAME].value
    return _format_prompt(ConversationStage.COLLECT_EMAIL, info)


def _handle_collect_email(conv: Conversation, user_msg: str) -> str:
    stripped = user_msg.strip()
    if _is_blank(stripped):
        return "Please provide a valid **email address** so we can reach you."
    if "@" not in stripped or "." not in stripped.split("@")[-1]:
        return (
            "That doesn't look like a valid email address. "
            "Please enter your **email** in the format: name@example.com"
        )
    info = dict(conv.collected_info)
    info["email"] = stripped
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_EMAIL].value
    return _format_prompt(ConversationStage.COLLECT_PHONE, info)


def _handle_collect_phone(conv: Conversation, user_msg: str) -> str:
    if _is_blank(user_msg):
        return "Please enter your **phone number** (or type 'skip' to proceed without it)."
    info = dict(conv.collected_info)
    info["phone"] = user_msg.strip()
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_PHONE].value
    return _format_prompt(ConversationStage.COLLECT_EXPERIENCE, info)


def _handle_collect_experience(conv: Conversation, user_msg: str) -> str:
    if _is_blank(user_msg):
        return "How many **years of professional experience** do you have? (e.g., 3 years)"
    info = dict(conv.collected_info)
    info["experience"] = user_msg.strip()
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_EXPERIENCE].value
    return _format_prompt(ConversationStage.COLLECT_ROLE, info)


def _handle_collect_role(conv: Conversation, user_msg: str) -> str:
    if _is_blank(user_msg):
        return "What **position(s)** are you applying for? (e.g., Backend Engineer, Data Scientist)"
    info = dict(conv.collected_info)
    info["desired_role"] = user_msg.strip()
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_ROLE].value
    return _format_prompt(ConversationStage.COLLECT_LOCATION, info)


def _handle_collect_location(conv: Conversation, user_msg: str) -> str:
    if _is_blank(user_msg):
        return "Please share your **current location** or preferred work location (e.g., New York, Remote)."
    info = dict(conv.collected_info)
    info["location"] = user_msg.strip()
    conv.collected_info = info  # type: ignore[assignment]
    conv.current_stage = _NEXT_STAGE[ConversationStage.COLLECT_LOCATION].value
    return _format_prompt(ConversationStage.COLLECT_TECH_STACK, info)


def _handle_collect_tech_stack(
    conv: Conversation, user_msg: str, db: Session
) -> tuple[str, list[QuestionItem]]:
    """
    Merged COLLECT_TECH_STACK + GENERATE_QUESTIONS handler.

    On a single message:
    1. Parse the tech stack from user input.
    2. Persist the candidate profile.
    3. Call the LLM to generate questions (JSON format).
    4. Persist CandidateTechStack + TechnicalQuestion rows.
    5. Advance stage to ANSWERING_QUESTIONS.

    Returns (reply_message, list_of_QuestionItems).
    """
    tech_stack: list[str] = [
        t.strip() for t in user_msg.replace(",", " ").split() if t.strip()
    ]
    if not tech_stack:
        return (
            "Please list at least one technology you are proficient in. "
            "For example: Python, Django, PostgreSQL, React.",
            [],
        )

    info = dict(conv.collected_info)
    info["tech_stack"] = tech_stack
    conv.collected_info = info  # type: ignore[assignment]

    # ── Persist candidate profile first (need candidate_id for FK) ────────────
    _persist_candidate(db, conv)
    db.flush()

    # ── Generate questions via LLM ────────────────────────────────────────────
    raw_questions = llm_service.generate_technical_questions(tech_stack, count=3)

    # Fallback if LLM failed or returned empty
    if not raw_questions:
        logger.warning("LLM returned no questions — using fallback questions.")
        raw_questions = llm_service._fallback_questions(tech_stack, count=3)

    # ── Persist to DB ─────────────────────────────────────────────────────────
    question_items = _persist_tech_stack_and_questions(db, conv, raw_questions)

    conv.current_stage = ConversationStage.ANSWERING_QUESTIONS.value

    if not question_items:
        return (
            "I had trouble generating questions. Please refresh and try again.",
            [],
        )

    reply = (
        f"Your tech stack has been recorded: **{', '.join(tech_stack)}**.\n\n"
        "I've generated technical interview questions for each technology. "
        "Please answer all of them in the form below and click **Submit All Answers**."
    )
    return reply, question_items


def _handle_answering_questions(_conv: Conversation, _user_msg: str) -> str:
    """
    Stub handler for the ANSWERING_QUESTIONS stage.

    The frontend hides the chat input during this stage, so users
    shouldn't send messages here. This handles edge cases (e.g., API calls).
    """
    return (
        "Please use the answer form below to submit your responses. "
        "The chat input is disabled during this stage."
    )


# ── Answer submission (called from routes) ────────────────────────────────────

def submit_answers(
    db: Session,
    session_id: str,
    answers: list[dict[str, Any]],
) -> tuple[str, ConversationStage]:
    """
    Validate and persist candidate answers, then transition session to ENDED.

    Parameters
    ----------
    db:       Active SQLAlchemy session.
    session_id: UUID of the conversation.
    answers:  List of {"question_id": int, "answer": str} dicts.

    Returns
    -------
    (reply_message, ENDED_stage)
    """
    conv = db.get(Conversation, session_id)
    if not conv:
        raise ValueError(f"Session {session_id!r} not found.")

    question_ids = [a["question_id"] for a in answers]

    # Fetch questions and validate they belong to this candidate
    questions = (
        db.query(TechnicalQuestion)
        .filter(
            TechnicalQuestion.id.in_(question_ids),
            TechnicalQuestion.candidate_id == conv.candidate_id,
        )
        .all()
    )

    found_ids = {q.id for q in questions}
    missing = set(question_ids) - found_ids
    if missing:
        raise ValueError(f"Invalid question IDs: {missing}")

    # Validate no blank answers
    answer_map = {a["question_id"]: a["answer"] for a in answers}
    for q in questions:
        ans = answer_map.get(q.id, "").strip()
        if not ans:
            raise ValueError(f"Answer for question {q.id} cannot be blank.")

    # Persist answers
    for q in questions:
        q.answer = answer_map[q.id].strip()

    # Transition to ENDED
    conv.current_stage = ConversationStage.ENDED.value
    info = conv.collected_info or {}
    name = info.get("name", "")
    reply = _format_prompt(ConversationStage.ENDED, {"name": name})
    _append_message(conv, "assistant", reply)

    db.commit()
    logger.info("Answers submitted and session %r transitioned to ENDED.", session_id)
    return reply, ConversationStage.ENDED


# ── Public entry point ────────────────────────────────────────────────────────

def process_message(
    db: Session,
    user_message: str,
    session_id: str | None = None,
) -> tuple[str, str, ConversationStage, bool, list[QuestionItem] | None]:
    """
    Process a user message through the FSM and return the bot's reply.

    Parameters
    ----------
    db:           Active SQLAlchemy session.
    user_message: Raw text from the user.
    session_id:   Optional existing session UUID.

    Returns
    -------
    (reply, session_id, current_stage, is_ended, questions)

    `questions` is a list of QuestionItem only when transitioning into
    ANSWERING_QUESTIONS; None for all other stages.
    """
    conv = _get_or_create_conversation(db, session_id)
    stage = ConversationStage(conv.current_stage)
    questions: list[QuestionItem] | None = None

    # ── Exit condition ────────────────────────────────────────────────────────
    if _is_exit(user_message):
        _append_message(conv, "user", user_message)
        reply = (
            "Thanks for using TalentScout! "
            "We hope to be in touch soon. Goodbye!"
        )
        _append_message(conv, "assistant", reply)
        conv.current_stage = ConversationStage.ENDED.value
        db.commit()
        return reply, conv.id, ConversationStage.ENDED, True, None

    # ── Already ended ─────────────────────────────────────────────────────────
    if stage == ConversationStage.ENDED:
        reply = "This session has already ended. Start a new session by refreshing the page."
        db.commit()
        return reply, conv.id, ConversationStage.ENDED, True, None

    # ── Append user message to history ────────────────────────────────────────
    _append_message(conv, "user", user_message)

    # ── Dispatch to stage handler ─────────────────────────────────────────────
    try:
        if stage == ConversationStage.GREETING:
            reply = _handle_greeting(conv, user_message)

        elif stage == ConversationStage.COLLECT_NAME:
            reply = _handle_collect_name(conv, user_message)

        elif stage == ConversationStage.COLLECT_EMAIL:
            reply = _handle_collect_email(conv, user_message)

        elif stage == ConversationStage.COLLECT_PHONE:
            reply = _handle_collect_phone(conv, user_message)

        elif stage == ConversationStage.COLLECT_EXPERIENCE:
            reply = _handle_collect_experience(conv, user_message)

        elif stage == ConversationStage.COLLECT_ROLE:
            reply = _handle_collect_role(conv, user_message)

        elif stage == ConversationStage.COLLECT_LOCATION:
            reply = _handle_collect_location(conv, user_message)

        elif stage == ConversationStage.COLLECT_TECH_STACK:
            reply, questions = _handle_collect_tech_stack(conv, user_message, db)

        elif stage == ConversationStage.ANSWERING_QUESTIONS:
            reply = _handle_answering_questions(conv, user_message)

        else:
            reply = "I'm not sure how to handle that. Let's continue from where we left off."

    except Exception as exc:  # noqa: BLE001
        logger.exception("Stage handler failed: %s", exc)
        db.rollback()
        reply = (
            "Sorry, I hit an unexpected issue. "
            "Let's continue — could you repeat your last message?"
        )
        questions = None

    # ── Append assistant reply to history ─────────────────────────────────────
    _append_message(conv, "assistant", reply)

    current_stage = ConversationStage(conv.current_stage)
    is_ended = current_stage == ConversationStage.ENDED

    db.commit()
    return reply, conv.id, current_stage, is_ended, questions
