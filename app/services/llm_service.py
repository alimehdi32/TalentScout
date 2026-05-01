"""
LLM Service — OpenAI-compatible abstraction.

This module is the ONLY place that talks to the LLM.
Swap the vendor (e.g., Azure OpenAI, Groq, Ollama) by
changing OPENAI_API_BASE in .env — no code changes needed.

Responsibilities:
- Build structured system prompts
- Generate technical questions per tech stack (returns structured JSON)
- Manage conversation-level context
"""

import json
import logging
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Client (lazy singleton) ───────────────────────────────────────────────────
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return the shared OpenAI-compatible client, creating it once."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            timeout=settings.LLM_TIMEOUT,
        )
    return _client


# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_BASE = """You are TalentScout, a professional AI hiring assistant.
Your job is to conduct structured candidate screening interviews in a warm,
conversational, and encouraging tone.

Rules:
- Be concise and professional.
- Never fabricate facts, tools, or technologies.
- Never ask for information you already have.
- Stay on-topic: hiring interviews only.
- If the user asks something off-topic, politely redirect them.
"""

_QUESTION_GEN_PROMPT = """
You are a senior technical interviewer at a recruitment agency.
The candidate has declared the following tech stack: {tech_stack}.

Generate exactly {count} technical interview questions FOR EACH technology listed above.

Return ONLY a valid JSON array. Each element must have exactly two string keys:
  "technology" — the exact technology name from the list above
  "question"   — one concise interview question about that technology

Example (for tech_stack = "Python, Django"):
[
  {{"technology": "Python", "question": "What is the difference between a list and a tuple in Python?"}},
  {{"technology": "Python", "question": "Explain how Python's GIL affects multi-threaded programs."}},
  {{"technology": "Python", "question": "How does Python manage memory using reference counting?"}},
  {{"technology": "Django", "question": "How does Django's ORM differ from writing raw SQL queries?"}},
  {{"technology": "Django", "question": "Explain the role of Django middleware in the request/response cycle."}},
  {{"technology": "Django", "question": "What is the difference between select_related and prefetch_related?"}}
]

Rules:
- Include EXACTLY {count} questions per technology — no more, no less.
- ONLY use technologies from the provided list — do not invent others.
- Mix difficulty: roughly 60% beginner/intermediate, 40% intermediate/advanced.
- Keep each question to one concise sentence.
- Return ONLY the JSON array — no markdown fences, no preamble, no explanation.
"""

# ── Sentiment analysis scaffold ───────────────────────────────────────────────

_SENTIMENT_PROMPT = """
Analyse the sentiment of the following message.
Return JSON: {{"sentiment": "positive"|"neutral"|"negative", "score": float 0-1}}

Message: """


# ── Public API ────────────────────────────────────────────────────────────────

def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Send a list of messages to the LLM and return the assistant reply.

    Parameters
    ----------
    messages:
        OpenAI-format message list, e.g. [{"role": "user", "content": "..."}]
    temperature:
        Sampling temperature. Defaults to settings value.
    max_tokens:
        Max tokens to generate. Defaults to settings value.

    Returns
    -------
    str
        The assistant's reply, or a safe fallback message on error.
    """
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature or settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        )
        logger.debug("LLM response choices: %s", response.choices)
        return response.choices[0].message.content or ""

    except RateLimitError:
        logger.warning("LLM rate limit hit.")
        return (
            "I'm experiencing high demand right now. "
            "Please give me a moment and try again."
        )
    except APITimeoutError:
        logger.warning("LLM request timed out.")
        return "The request took too long. Please try again in a moment."
    except APIConnectionError as exc:
        logger.error("LLM connection error: %s", exc)
        return (
            "I'm having trouble connecting to my AI brain. "
            "Please check your connection and try again."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected LLM error: %s", exc)
        return (
            "Something unexpected happened on my end. "
            "Let's continue — please repeat your last message."
        )


def build_system_message() -> dict[str, str]:
    """Return the base system message dict."""
    return {"role": "system", "content": _SYSTEM_PROMPT_BASE}


def generate_technical_questions(
    tech_stack: list[str],
    count: int = 3,
) -> list[dict[str, str]]:
    """
    Generate `count` technical questions **per technology** in `tech_stack`.

    The LLM is instructed to return a JSON array of
    {"technology": ..., "question": ...} objects — one per question,
    grouped by technology.

    Parameters
    ----------
    tech_stack:
        List of technology names, e.g. ["Python", "FastAPI"].
    count:
        Number of questions per technology (default 3, range 3-5 per assignment).

    Returns
    -------
    list[dict[str, str]]
        List of {"technology": str, "question": str} dicts.
        Returns an empty list on parse failure (caller should use fallback).
    """
    if not tech_stack:
        return []

    logger.info("Generating %d questions per tech for: %s", count, tech_stack)

    tech_str = ", ".join(tech_stack)
    prompt = _QUESTION_GEN_PROMPT.format(count=count, tech_stack=tech_str)
    messages = [{"role": "user", "content": prompt}]
    raw = chat_completion(messages, temperature=0.3, max_tokens=2048)

    logger.debug("Raw question JSON from LLM: %r", raw)

    # Strip markdown fences if the model wrapped the JSON anyway
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()

    if not stripped.startswith("["):
        logger.warning("Question generation returned non-JSON: %r", raw)
        return []

    try:
        data: list[dict[str, str]] = json.loads(stripped)
        if isinstance(data, list):
            # Filter out malformed entries
            valid = [
                item for item in data
                if isinstance(item, dict)
                and item.get("technology")
                and item.get("question")
            ]
            logger.info("Parsed %d valid questions from LLM output.", len(valid))
            return valid
        return []
    except json.JSONDecodeError:
        logger.warning("Failed to parse question JSON: %r", raw)
        return []


def _fallback_questions(tech_stack: list[str], count: int = 3) -> list[dict[str, str]]:
    """
    Generate generic fallback questions when the LLM call fails.

    Used internally by chat_service so the session never gets stuck.
    """
    templates = [
        "What are the core features and advantages of {tech}?",
        "Describe a real project where you applied {tech} and the challenges you faced.",
        "What are the best practices you follow when working with {tech}?",
        "How does {tech} compare to similar tools or frameworks in its ecosystem?",
        "What performance considerations should a developer keep in mind with {tech}?",
    ]
    questions = []
    for tech in tech_stack:
        for template in templates[:count]:
            questions.append({"technology": tech, "question": template.format(tech=tech)})
    return questions


def analyse_sentiment(text: str) -> dict[str, Any]:
    """
    Scaffold: analyse sentiment of a message.

    Only runs when ENABLE_SENTIMENT_ANALYSIS=true in .env.
    Returns {"sentiment": "neutral", "score": 0.5} by default.
    """
    if not settings.ENABLE_SENTIMENT_ANALYSIS:
        return {"sentiment": "neutral", "score": 0.5}

    prompt = _SENTIMENT_PROMPT + text
    raw = chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=64,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"sentiment": "neutral", "score": 0.5}
