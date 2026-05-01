"""
TalentScout — Streamlit Frontend

A clean, professional chat interface that communicates with the
FastAPI backend. All state is stored in Streamlit's session_state.

Run with:
    streamlit run frontend/streamlit_app.py
"""

import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

# ── Exit keywords (checked client-side to avoid unnecessary API calls) ────────
EXIT_KEYWORDS = frozenset({
    "exit", "quit", "bye", "goodbye", "stop", "end", "done", "finish", "terminate",
})

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TalentScout — AI Hiring Assistant",
    page_icon="T",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        box-sizing: border-box;
    }

    #MainMenu, footer, header { visibility: hidden; }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 760px !important;
    }

    .stApp { background: #000000; min-height: 100vh; }

    /* ── Header ── */
    .ts-header {
        text-align: center;
        padding: 1.2rem 0 0.6rem;
        border-bottom: 1px solid #1a1a1a;
        margin-bottom: 1rem;
    }
    .ts-title { font-size: 1.6rem; font-weight: 700; color: #ffffff; letter-spacing: -0.02em; margin: 0; }
    .ts-subtitle { color: #555555; font-size: 0.82rem; margin-top: 0.25rem; font-weight: 400; }

    /* ── Stage badge ── */
    .stage-badge {
        display: inline-block;
        background: #111111;
        border: 1px solid #2a2a2a;
        color: #888888;
        font-size: 0.68rem;
        font-weight: 600;
        padding: 0.18rem 0.65rem;
        border-radius: 999px;
        letter-spacing: 0.07em;
        text-transform: uppercase;
    }

    /* ── Chat bubbles ── */
    .msg-user { display: flex; justify-content: flex-end; margin: 0.5rem 0; }
    .msg-assistant { display: flex; justify-content: flex-start; margin: 0.5rem 0; }
    .bubble {
        max-width: 78%;
        padding: 0.7rem 1rem;
        border-radius: 14px;
        line-height: 1.6;
        font-size: 0.9rem;
        word-wrap: break-word;
        white-space: pre-wrap;
    }
    .bubble-user { background: #ffffff; color: #000000; border-bottom-right-radius: 3px; }
    .bubble-assistant {
        background: #111111;
        border: 1px solid #222222;
        color: #cccccc;
        border-bottom-left-radius: 3px;
    }

    /* ── Answer form ── */
    .answer-form-header {
        margin: 1.5rem 0 0.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #1a1a1a;
    }
    .answer-form-title { font-size: 1rem; font-weight: 600; color: #ffffff; margin: 0; }
    .answer-form-sub { color: #555555; font-size: 0.8rem; margin-top: 0.2rem; }
    .tech-heading {
        font-size: 0.78rem;
        font-weight: 700;
        color: #888888;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.2rem 0 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #1a1a1a;
    }
    .question-text {
        color: #cccccc;
        font-size: 0.88rem;
        line-height: 1.5;
        margin-bottom: 0.4rem;
        font-weight: 500;
    }

    /* ── Ended banner ── */
    .ended-banner {
        text-align: center;
        padding: 1.2rem 1rem;
        background: #0d0d0d;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        color: #888888;
        font-size: 0.9rem;
        margin: 1rem 0;
    }

    /* ── Text input ── */
    .stTextInput > div > div > input {
        background: #0d0d0d !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 0.65rem 1rem !important;
    }
    .stTextInput > div > div > input::placeholder { color: #444444 !important; }
    .stTextInput > div > div > input:focus {
        border-color: #444444 !important;
        box-shadow: none !important;
    }

    /* ── Text area (answers) ── */
    .stTextArea > div > div > textarea {
        background: #0d0d0d !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.88rem !important;
        padding: 0.65rem 1rem !important;
        resize: vertical;
    }
    .stTextArea > div > div > textarea::placeholder { color: #444444 !important; }
    .stTextArea > div > div > textarea:focus {
        border-color: #444444 !important;
        box-shadow: none !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #ffffff !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.65rem 1.4rem !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.88rem !important;
        width: 100%;
        transition: background 0.15s;
    }
    .stButton > button:hover { background: #e0e0e0 !important; }

    /* ── Divider ── */
    hr { border-color: #1a1a1a !important; margin: 0.6rem 0 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #080808 !important;
        border-right: 1px solid #1a1a1a;
    }
    section[data-testid="stSidebar"] * { color: #999999 !important; }

    /* ── Responsive ── */
    @media (max-width: 600px) {
        .ts-title { font-size: 1.2rem; }
        .bubble { max-width: 90%; font-size: 0.85rem; }
        .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────

def init_session() -> None:
    """Initialise Streamlit session state on first load."""
    defaults: dict[str, Any] = {
        "session_id": None,
        "messages": [],         # list of {"role": str, "content": str}
        "stage": "greeting",
        "is_ended": False,
        "started": False,
        "input_counter": 0,     # incremented after each send to force input reset
        "questions": [],        # list of {id, technology, question_text} — set at ANSWERING_QUESTIONS
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session()


# ── Backend communication ─────────────────────────────────────────────────────

def send_message(user_msg: str) -> dict[str, Any] | None:
    """POST to /api/v1/chat and return the parsed JSON response."""
    payload = {"message": user_msg, "session_id": st.session_state.session_id}
    try:
        resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to the backend at `{BACKEND_URL}`.")
        return None
    except requests.exceptions.Timeout:
        st.error("The request timed out. The LLM may be slow — please try again.")
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"Server error: {exc.response.status_code} — {exc.response.text}")
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unexpected error: {exc}")
        return None


def post_answers(answers: dict[int, str]) -> dict[str, Any] | None:
    """POST to /api/v1/answers and return the parsed JSON response."""
    payload = {
        "session_id": st.session_state.session_id,
        "answers": [
            {"question_id": qid, "answer": ans}
            for qid, ans in answers.items()
        ],
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/answers", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to the backend at `{BACKEND_URL}`.")
        return None
    except requests.exceptions.Timeout:
        st.error("The request timed out. Please try submitting again.")
        return None
    except requests.exceptions.HTTPError as exc:
        detail = exc.response.json().get("detail", exc.response.text)
        st.error(f"Submission error: {detail}")
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unexpected error: {exc}")
        return None


# ── UI rendering ──────────────────────────────────────────────────────────────

def render_header() -> None:
    st.markdown(
        """
        <div class="ts-header">
            <p class="ts-title">TalentScout</p>
            <p class="ts-subtitle">AI Hiring Assistant &nbsp;·&nbsp; Technical Screening</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_badge() -> None:
    stage_label = st.session_state.stage.replace("_", " ").title()
    st.markdown(
        f'<div style="text-align:center;margin:0.4rem 0 0.8rem;">'
        f'<span class="stage-badge">{stage_label}</span></div>',
        unsafe_allow_html=True,
    )


def render_messages() -> None:
    """Render the full conversation as styled chat bubbles."""
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.markdown(
                f'<div class="msg-user">'
                f'<div class="bubble bubble-user">{content}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="msg-assistant">'
                f'<div class="bubble bubble-assistant">{content}</div></div>',
                unsafe_allow_html=True,
            )


def render_answer_form() -> None:
    """
    Render the dedicated technical Q&A form.

    Shows questions grouped under their technology heading. Each question
    has a text_area below it. A single "Submit All Answers" button at the
    bottom validates all fields are filled before posting to /answers.
    """
    questions: list[dict[str, Any]] = st.session_state.get("questions", [])
    if not questions:
        st.warning("No questions found. Please refresh and try again.")
        return

    st.markdown(
        """
        <div class="answer-form-header">
            <p class="answer-form-title">Technical Interview Questions</p>
            <p class="answer-form-sub">
                Answer all questions below, then click <strong>Submit All Answers</strong>.
                All fields are required.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Group questions by technology (preserve insertion order)
    by_tech: dict[str, list[dict[str, Any]]] = {}
    for q in questions:
        tech = q["technology"]
        by_tech.setdefault(tech, []).append(q)

    # Collect answer values
    collected_answers: dict[int, str] = {}
    for tech, qs in by_tech.items():
        st.markdown(f'<p class="tech-heading">{tech}</p>', unsafe_allow_html=True)
        for idx, q in enumerate(qs, start=1):
            st.markdown(
                f'<p class="question-text">{idx}. {q["question_text"]}</p>',
                unsafe_allow_html=True,
            )
            answer = st.text_area(
                label=f"answer_{q['id']}",
                placeholder="Type your answer here...",
                key=f"ans_{q['id']}",
                height=90,
                label_visibility="collapsed",
            )
            collected_answers[q["id"]] = answer

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if st.button("Submit All Answers", key="submit_answers_btn"):
        blank_count = sum(1 for ans in collected_answers.values() if not ans.strip())
        if blank_count:
            st.error(
                f"{blank_count} answer(s) are empty. Please answer all questions before submitting."
            )
        else:
            with st.spinner("Submitting your answers..."):
                response = post_answers(collected_answers)
            if response:
                st.session_state.is_ended = True
                st.session_state.stage = "ended"
                st.session_state.messages.append(
                    {"role": "assistant", "content": response["message"]}
                )
                st.rerun()


def render_input_area() -> tuple[str, bool]:
    """
    Render message input and send button.

    The text_input key is derived from `input_counter` so that incrementing
    the counter on each send forces Streamlit to render a fresh, empty input.
    """
    st.markdown("---")
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input(
            label="Message",
            placeholder="Type your message here...",
            key=f"user_input_{st.session_state.input_counter}",
            label_visibility="collapsed",
        )
    with col2:
        send_clicked = st.button("Send", key="send_btn")
    return user_input, send_clicked


def render_ended_banner() -> None:
    st.markdown(
        """
        <div class="ended-banner">
            Interview session completed. Thank you for using <strong>TalentScout</strong>.<br>
            Refresh the page to start a new session.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Message handlers ──────────────────────────────────────────────────────────

def _is_exit_input(text: str) -> bool:
    """Return True if the user's message is a session-termination keyword."""
    return text.strip().lower() in EXIT_KEYWORDS


def handle_send(user_input: str) -> None:
    """Append the user message, call backend, append assistant reply."""
    if not user_input.strip():
        return

    # ── Frontend exit check — no network call needed ──────────────────────────
    if _is_exit_input(user_input):
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Thanks for using TalentScout! We hope to be in touch soon. Goodbye!",
        })
        st.session_state.is_ended = True
        st.session_state.stage = "ended"
        st.session_state.input_counter += 1
        return

    # Auto-start: bootstrap greeting on first message
    if not st.session_state.started:
        st.session_state.started = True
        _bootstrap_greeting()

    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("Thinking..."):
        response = send_message(user_input)

    if response:
        st.session_state.session_id = response["session_id"]
        st.session_state.stage = response["stage"]
        st.session_state.is_ended = response.get("is_ended", False)
        st.session_state.messages.append(
            {"role": "assistant", "content": response["message"]}
        )
        # Store questions when backend transitions to ANSWERING_QUESTIONS
        if response.get("questions"):
            st.session_state.questions = response["questions"]

    st.session_state.input_counter += 1


def _bootstrap_greeting() -> None:
    """Send a dummy 'hello' to kick-start the FSM on first load."""
    if st.session_state.session_id is not None:
        return
    with st.spinner("Starting session..."):
        response = send_message("hello")
    if response:
        st.session_state.session_id = response["session_id"]
        st.session_state.stage = response["stage"]
        st.session_state.is_ended = response.get("is_ended", False)
        st.session_state.messages.append(
            {"role": "assistant", "content": response["message"]}
        )


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## TalentScout")
        st.markdown("**AI Hiring Assistant**")
        st.divider()
        if st.session_state.session_id:
            st.markdown(f"**Session ID**\n\n`{st.session_state.session_id}`")
            st.markdown(f"**Stage:** `{st.session_state.stage}`")
            st.markdown(f"**Messages:** {len(st.session_state.messages)}")
        else:
            st.info("No active session.")
        st.divider()
        st.markdown("### Tips")
        st.markdown(
            "- Type **exit** or **bye** at any point to end the session.\n"
            "- All profile fields are optional — type 'skip' to pass.\n"
        )
        st.divider()
        if st.button("New Session"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    render_sidebar()
    render_header()

    # Auto-bootstrap: show greeting on first visit
    if not st.session_state.started and not st.session_state.messages:
        st.session_state.started = True
        _bootstrap_greeting()
        st.rerun()

    render_stage_badge()
    render_messages()

    if st.session_state.is_ended:
        render_ended_banner()
    elif st.session_state.stage == "answering_questions":
        # Show the dedicated Q&A form — chat input is hidden during this stage
        render_answer_form()
    else:
        user_input, send_clicked = render_input_area()
        if send_clicked and user_input:
            handle_send(user_input)
            st.rerun()


if __name__ == "__main__":
    main()
