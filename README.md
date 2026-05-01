# TalentScout — AI Hiring Assistant

> An intelligent chatbot that conducts structured candidate screening interviews,
> collects profile information, and generates personalised technical questions based
> on the candidate's declared tech stack — powered by large language models.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage Guide](#usage-guide)
6. [Technical Details](#technical-details)
7. [Prompt Design](#prompt-design)
8. [Database Schema](#database-schema)
9. [Challenges & Solutions](#challenges--solutions)

---

## Project Overview

TalentScout is a conversational AI hiring assistant built for **TalentScout Recruitment Agency**.
It automates the initial candidate screening process by:

- Greeting candidates and explaining its purpose
- Collecting essential profile information through a guided conversation
- Generating **3 tailored technical questions per declared technology** using an LLM
- Presenting those questions in a dedicated answer form
- Storing every question and its answer in a normalised database
- Gracefully concluding the session with next-steps information

The system is built with a **FastAPI backend** and a **Streamlit frontend**, connected via a
clean REST API. It uses any OpenAI-compatible LLM (Groq, Azure OpenAI, Ollama, etc.) configurable
through a single environment variable — no code changes required to swap providers.

---

## Features

| Feature | Description |
|---|---|
| Guided FSM conversation | 9-stage finite state machine: Greeting → Info collection → Tech stack → Questions → Answers → End |
| LLM-generated questions | 3 questions per technology, grouped by technology, via structured JSON prompt |
| Per-question answer form | Dedicated UI section with one text field per question; all answers required before submission |
| Input validation & fallbacks | Every field validates input and re-prompts on blank/invalid entries; email format checked |
| Frontend exit detection | Exit keywords (`bye`, `exit`, etc.) handled client-side — no network call needed |
| Persistent sessions | Full message history + candidate profile stored in PostgreSQL across page refreshes |
| Normalised DB schema | Separate tables for tech stack entries and technical questions with candidate FKs |
| Vendor-agnostic LLM | Works with Groq, Azure OpenAI, Ollama, or any OpenAI-compatible API endpoint |
| Safe LLM fallbacks | Falls back to generic questions if the LLM returns malformed output |
| Clean dark UI | Responsive, pure-black Streamlit interface — no emojis, Inter font, mobile-friendly |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                       │
│  ┌──────────────┐  ┌────────────────────────────────────┐   │
│  │  Chat UI     │  │  Answer Form (ANSWERING_QUESTIONS)  │   │
│  │  (bubbles)   │  │  Groups questions by technology     │   │
│  └──────┬───────┘  └──────────────┬─────────────────────┘   │
│         │ POST /chat              │ POST /answers             │
└─────────┼─────────────────────────┼───────────────────────────┘
          ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  chat_service.py — FSM Orchestrator                    │ │
│  │  Stages: GREETING → COLLECT_* → COLLECT_TECH_STACK     │ │
│  │          → ANSWERING_QUESTIONS → ENDED                 │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼─────────────────────────────────┐ │
│  │  llm_service.py — LLM Abstraction                      │ │
│  │  Generates questions as structured JSON                 │ │
│  └──────────────────────┬─────────────────────────────────┘ │
└─────────────────────────┼────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                      │
│  candidates · conversations · candidate_tech_stack           │
│  technical_questions                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- An API key for any OpenAI-compatible LLM provider (Groq is free and recommended)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd talentscout
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your values:

```ini
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/talentscout

# LLM Provider (Groq example — get a free key at console.groq.com)
OPENAI_API_KEY=gsk_your_groq_key_here
OPENAI_API_BASE=https://api.groq.com/openai/v1
MODEL_NAME=llama3-8b-8192

# App settings (leave defaults for local dev)
APP_NAME=TalentScout
APP_VERSION=1.0.0
DEBUG=true
```

> **Using Ollama (fully local, free)?**
> ```ini
> OPENAI_API_BASE=http://localhost:11434/v1
> OPENAI_API_KEY=ollama
> MODEL_NAME=llama3.2
> ```

### 5. Create the PostgreSQL database

```sql
-- Run in psql or pgAdmin
CREATE DATABASE talentscout;
```

All tables are created **automatically** on first startup — no migration tool needed.

### 6. Run the application

Open **two terminals** with the virtual environment active:

**Terminal 1 — Backend:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
streamlit run frontend/streamlit_app.py
```

| Service | URL |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |

---

## Usage Guide

Once both servers are running, open **http://localhost:8501** in your browser.

### Conversation Flow

The chatbot walks through the following stages automatically:

| Stage | What Happens |
|---|---|
| **Greeting** | Bot introduces itself, explains its purpose, and mentions it handles data securely |
| **Full Name** | Candidate enters their full name |
| **Email Address** | Email validated for correct format (`name@domain.com`) |
| **Phone Number** | Phone number collected (can type `skip` to pass) |
| **Years of Experience** | Numeric or text experience value collected |
| **Desired Position(s)** | Role(s) the candidate is applying for |
| **Current Location** | City, country, or remote preference |
| **Tech Stack** | Comma or space-separated list of technologies |
| **Technical Questions** | LLM generates 3 questions per technology — answer form appears |
| **Answer Submission** | Candidate fills all answers and clicks **Submit All Answers** |
| **End** | Bot thanks the candidate and explains next steps |

### Tips

- Type `exit`, `quit`, or `bye` at **any point** to end the session immediately (handled client-side — no delay).
- Blank or invalid inputs are caught and re-prompted — you cannot accidentally advance with empty fields.
- The email field validates format; a helpful error is shown for invalid entries.
- The tech stack field accepts comma-separated or space-separated input: `Python Django PostgreSQL` or `Python, Django, PostgreSQL`.
- Click **New Session** in the sidebar to start a completely fresh session.
- All answers in the technical Q&A form are required — the Submit button is blocked until every field is filled.

---

## Technical Details

### Libraries & Tools

| Layer | Library | Version | Purpose |
|---|---|---|---|
| Backend | FastAPI | 0.115+ | REST API framework |
| Backend | Uvicorn | latest | ASGI server |
| Backend | SQLAlchemy | 2.0 | ORM + DB session management |
| Backend | Pydantic v2 | 2.x | Request/response validation |
| Backend | psycopg2-binary | latest | PostgreSQL driver |
| LLM Client | openai | latest | OpenAI-compatible SDK (vendor-agnostic) |
| Frontend | Streamlit | 1.41+ | Interactive UI |
| Frontend | requests | latest | HTTP client for backend calls |
| Config | python-dotenv | latest | `.env` file loading |
| Config | pydantic-settings | latest | Typed settings with env var support |
| Database | PostgreSQL | 14+ | Persistent storage |

### Model Details

The system is LLM-agnostic. Any model that is compatible with the OpenAI Chat Completions API can be used:

| Provider | Recommended Model | Notes |
|---|---|---|
| Groq | `llama3-8b-8192` | Free tier, very fast |
| Groq | `mixtral-8x7b-32768` | Better quality, still free |
| OpenAI | `gpt-4o-mini` | Cost-effective, high quality |
| Ollama | `llama3.2` | Fully local, no API key needed |
| Azure OpenAI | `gpt-4o` | Enterprise option |

### Architectural Decisions

**Finite State Machine (FSM):** The conversation is controlled by a 9-stage FSM in `chat_service.py`.
Each stage has a dedicated handler that validates input, stores data, and advances to the next stage.
This ensures the conversation always progresses in a predictable, testable order.

**Single LLM call per session:** The LLM is invoked exactly once — at the tech stack submission stage.
All other stages perform direct string storage. This minimises API costs and latency significantly
compared to calling the LLM on every field.

**Stateless backend, stateful DB:** The FastAPI backend is fully stateless. All state (conversation
history, collected info, current stage) lives in PostgreSQL. This makes horizontal scaling trivial.

**Normalised question storage:** Rather than storing questions as a text blob, each question is a
separate row in `technical_questions` with FKs to both the candidate and the specific technology.
This allows querying questions by technology, tracking answer rates, and future analytics.

**Frontend exit detection:** Exit keywords are checked client-side before any network call.
This eliminates a full round-trip for what is the most latency-sensitive interaction in the app.

---

## Prompt Design

Three distinct prompts are used, each tuned for its specific task:

### 1. System Prompt — Conversation Guard

Applied as a persistent system message. Defines the bot's identity, tone (warm, professional),
and hard behavioural constraints:
- Stay on-topic: hiring interviews only
- Never fabricate technologies or facts
- Never ask for information already collected
- Politely redirect off-topic questions

### 2. Technical Question Generation Prompt

This is the **primary LLM call** and the most carefully engineered prompt in the system.

**Design goals:**
- Produce questions **per technology**, not a flat generic list
- Return **structured JSON** so the backend can parse and store individual questions
- Enforce exact question count per technology
- Apply a difficulty distribution (60% beginner/intermediate, 40% advanced)
- Prevent the model from wrapping output in markdown fences

**Prompt structure:**
```
You are a senior technical interviewer at a recruitment agency.
The candidate has declared the following tech stack: {tech_stack}.

Generate exactly {count} technical interview questions FOR EACH technology listed above.

Return ONLY a valid JSON array. Each element must have exactly two string keys:
  "technology" — the exact technology name from the list above
  "question"   — one concise interview question about that technology
...
```

The JSON output format was chosen over markdown headings because:
1. It can be reliably parsed programmatically
2. Each question can be stored as an individual DB row
3. It's immune to LLM formatting variation (e.g., different heading levels)

**Fallback:** If the LLM returns malformed output, `_fallback_questions()` generates
generic but meaningful questions (key features, past experience, best practices) for
each technology — ensuring the session never gets stuck.

### 3. Extraction Prompt (Scaffolded)

An extraction prompt exists in `llm_service.py` for parsing structured fields (name,
email, phone, etc.) from freeform text. In the current implementation, collection stages
store user input directly to eliminate unnecessary LLM calls. The extraction prompt is
retained as a utility for potential future use (e.g., re-parsing conversational input).

---

## Database Schema

```
candidates
  id            SERIAL PRIMARY KEY
  name          VARCHAR(255)
  email         VARCHAR(255) UNIQUE
  phone         VARCHAR(50)
  experience    VARCHAR(100)
  desired_role  VARCHAR(255)
  location      VARCHAR(255)
  tech_stack    JSONB             -- denormalised copy for quick reads
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

candidate_tech_stack
  id            SERIAL PRIMARY KEY
  candidate_id  INTEGER  → candidates.id  (CASCADE DELETE)
  technology    VARCHAR(255)

technical_questions
  id            SERIAL PRIMARY KEY
  candidate_id  INTEGER  → candidates.id          (CASCADE DELETE)
  tech_stack_id INTEGER  → candidate_tech_stack.id (CASCADE DELETE)
  question_text TEXT
  answer        TEXT     -- NULL until candidate submits; required on submission
  created_at    TIMESTAMPTZ

conversations
  id            VARCHAR(36) PRIMARY KEY  -- UUID
  candidate_id  INTEGER  → candidates.id (SET NULL on delete)
  messages      JSONB    -- full message history [{role, content}, ...]
  current_stage VARCHAR(50)
  collected_info JSONB   -- partial data during collection
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ
```

---

## Challenges & Solutions

### 1. LLM Called on Every Field Input

**Problem:** The initial design called `extract_candidate_info()` — a full LLM API call — on
every single field submission (name, email, phone, etc.), resulting in 6+ API calls per session
before even reaching the question generation step.

**Solution:** Removed all per-field LLM calls. Each collection stage handler now stores
`user_msg.strip()` directly. The LLM is invoked exactly **once** per session — at the tech
stack submission — reducing API costs by ~85%.

---

### 2. Duplicate Candidate Records (UniqueViolation)

**Problem:** Submitting the same email twice caused a PostgreSQL `UniqueViolation` crash because
the code always attempted an `INSERT` regardless of whether the email already existed.

**Solution:** Implemented an upsert pattern in `_persist_candidate()` — the function first
queries `candidates` by email, updates the existing row if found, and only inserts a new row
for previously unseen emails.

---

### 3. Stale Value Pre-filling in Streamlit Text Input

**Problem:** After submitting a message, Streamlit's `st.text_input` retained the previous
value in session state and pre-filled the next question's input box with the last answer.

**Solution:** Added `input_counter` to session state, incremented after every send. The input
widget key is `f"user_input_{input_counter}"` — a key change forces Streamlit to treat it as
a brand-new widget on each rerun, rendering it blank.

---

### 4. LLM Returning Non-JSON for Structured Prompts

**Problem:** Under rate limiting or connection errors, the LLM returned human-readable fallback
strings instead of the expected JSON, causing `json.loads()` to raise an exception.

**Solution:** Added defensive parsing in both the extraction and question generation functions:
- Check that the response starts with `[` or `{` before attempting to parse
- Strip markdown code fences if the model wrapped output in them anyway
- Return `{}` or `[]` on failure, with a `_fallback_questions()` safety net for question generation

---

### 5. No Validation on User Inputs

**Problem:** Users entering blank, single-character, or clearly invalid input (e.g., `"a"` as
their name, or `"abc"` as an email) would silently advance the FSM with garbage data.

**Solution:** Added a `_is_blank()` helper and per-stage validation in all 7 collection handlers.
The email handler additionally validates the `@domain.tld` format. Invalid inputs return a
contextual re-prompt message without advancing the stage.

---

### 6. Technical Questions Stored as a Text Blob

**Problem:** The original design stored all generated questions as a single text string in the
conversation message history — making it impossible to associate individual answers with
individual questions or query questions by technology.

**Solution:** Changed the LLM to return structured JSON (`[{"technology": ..., "question": ...}]`),
then parsed and stored each question as an individual row in `technical_questions` with foreign
keys to both the candidate and the technology. Answers are stored in the same row when submitted.

---

## Security Notes

- **`.env` is never committed** — it is listed in `.gitignore`
- Candidate data is stored in a private PostgreSQL instance, not exposed via any public endpoint
- CORS is configured via `ALLOWED_ORIGINS` in `.env` — restrict to your domain in production
- Rotate `SECRET_KEY` before any production deployment
- Email addresses are the only PII unique-indexed field; all others are optional

---

## Project Structure

```
talentscout/
├── app/
│   ├── main.py                  # FastAPI app factory, startup, CORS
│   ├── api/
│   │   └── routes.py            # POST /chat, POST /answers, GET /health
│   ├── core/
│   │   ├── config.py            # Typed settings (pydantic-settings + .env)
│   │   └── security.py          # Auth scaffold
│   ├── models/
│   │   └── candidate.py         # SQLAlchemy ORM: Candidate, CandidateTechStack,
│   │                            #   TechnicalQuestion, Conversation
│   ├── schemas/
│   │   └── candidate.py         # Pydantic schemas: ChatRequest/Response,
│   │                            #   QuestionItem, SubmitAnswersRequest, FSM enum
│   ├── services/
│   │   ├── llm_service.py       # LLM abstraction: JSON question generation,
│   │   │                        #   fallback questions, sentiment scaffold
│   │   └── chat_service.py      # FSM orchestrator, answer submission
│   └── db/
│       ├── base.py              # SQLAlchemy declarative base
│       └── session.py           # Engine + get_db() dependency
├── frontend/
│   └── streamlit_app.py         # Streamlit UI: chat bubbles + answer form
├── .env.example                 # Environment variable template
├── requirements.txt
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
