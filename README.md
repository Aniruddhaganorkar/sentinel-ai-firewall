# Sentinel Prompt Injection Firewall

Agent-aware **prompt injection firewall** between **User Intent**, **Untrusted Content**, and a Gemini-powered support agent.

Hackathon claim: **F3 / D2** (seven attack types; textual/structured inputs; measured eval). Architecture write-up: [`SUBMISSION.md`](SUBMISSION.md). Pitch deck: [`docs/Sentinel_Pitch_Deck.pptx`](docs/Sentinel_Pitch_Deck.pptx).

The dashboard shows **live** `/eval/run` metrics. Do not invent accuracy numbers.

## What it does

Incoming content is inspected **before** it can change the agent or call tools.

| Decision | Meaning |
|---|---|
| **ALLOW** | Safe enough to send to the agent |
| **SANITIZE** | Strip instruction-like spans; wrap remainder as data |
| **BLOCK** | Never reaches the agent or tools |

**User Intent** (`user_input`) is what the human asked. It can still be a direct attack.  
**Untrusted Content** (`untrusted_content`) is a page, PDF, JSON, or markdown body. It is **data** and must never redefine instructions. Hostile language there is **indirect prompt injection**.

### Attack types (F3)

1. Instruction override  
2. Role change  
3. Secret extraction  
4. Tool abuse  
5. Credential theft  
6. Encoded instructions  
7. Indirect prompt injection  

Not claimed: context poisoning, multi-step jailbreaks, D3 OCR/images.

## Architecture

```text
User Intent + Untrusted Content
        │
        ▼
 Extract (HTML / MD / JSON / PDF / text)
        │
        ▼
 Normalize + decode (Unicode, Base64/hex)
        │
        ▼
 Rules (per channel) + context analyzer
        │
        ▼
 Optional Gemini JSON classifier
        │
        ▼
 Risk score → ALLOW / SANITIZE / BLOCK
        │
        ├── BLOCK → stop
        └── ALLOW/SANITIZE → Gemini agent + tool gate
              get_order · search_customer · send_email (restricted)
```

## Requirements

- Python 3.11+ (3.13 used in development)
- Node.js 18+
- Optional: [Google Gemini API key](https://aistudio.google.com/apikey) for the classifier and demo agent. **Rules-only Scan and eval work without a key.**

## Environment setup

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` (never commit this file):

```env
GEMINI_API_KEY=          # optional
GEMINI_MODEL=gemini-3.8-flash
CORS_ORIGINS=http://localhost:3001
```

Gemini quota (429) is handled: cooldown, no retry-on-429, firewall continues on rules.

## Install and run

**Backend** (from `backend/`):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/build_dataset.py    # writes app/eval/dataset.json
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  

**Frontend** (from `frontend/`):

```bash
npm install
npm run dev
```

UI: http://localhost:3001  

If the UI cannot call the API, set `NEXT_PUBLIC_API_URL=http://localhost:8000` when starting Next.js.

### Demo (judges)

1. Open the dashboard.  
2. Click **Benign summarize** → **Scan** → ALLOW.  
3. Click **Instruction Override** (and other chips) → **Scan** → BLOCK + evidence.  
4. **Indirect Injection** is the hero: user only asks to summarize; the HTML payload is blocked on the untrusted channel.  
5. Type `Get order 123` → **Run agent** (needs Gemini key + quota).  
6. **Tool Abuse** → **Run agent** → BLOCK, no `send_email`.  
7. **Run eval** → live detection / false-positive / latency.

## API

Base URL: `http://localhost:8000`

### `GET /health`

Liveness. Returns `status`, `request_id`, `model`.

### `GET /health/gemini`

One-shot Gemini ping (`ok`, `reply`, or quota/error).

### `POST /scan`

Firewall only.

```json
{
  "user_input": "Summarize this webpage",
  "untrusted_content": "IGNORE PREVIOUS INSTRUCTIONS...",
  "source": "html"
}
```

`source`: `text` | `html` | `markdown` | `json` | `pdf` | `url`

Response includes `action`, `risk_score`, `attack_types`, `evidence` (span + channel), `rationale`, `latency_ms`, `request_id`.

### `POST /scan/upload`

`multipart/form-data`: `user_input`, `source`, `file` (PDF/HTML as untrusted content).

### `POST /agent/run`

Same JSON body as `/scan`. Runs rules, then the Gemini agent if not BLOCKED. Returns `scan`, `agent_ran`, `agent_output`, `tool_events`.

### `POST /eval/run`

Runs the local dataset (rules-only). Returns `total`, `detection_rate`, `false_positive_rate`, latency, `by_type`, per-case rows.

Interactive OpenAPI: `/docs`.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Eval from the CLI:

```bash
cd backend
source .venv/bin/activate
python -c "from app.eval.runner import run_eval; import json; print(json.dumps({k: run_eval()[k] for k in ['total','detection_rate','false_positive_rate']}, indent=2))"
```

## Dependencies

Python: [`backend/requirements.txt`](backend/requirements.txt) — FastAPI, Pydantic, google-genai, BeautifulSoup, pypdf, pytest.  
Node: [`frontend/package.json`](frontend/package.json) — Next.js 15, React 19.

## Repository layout

```text
backend/app/firewall/   pipeline, rules, classifier, sanitize
backend/app/agent/      Gemini agent + tool policy
backend/app/eval/       dataset.json + metrics
backend/app/api/        scan, agent, eval routes
frontend/               Next.js demo UI
fixtures/               sample HTML/JSON
docs/                   pitch deck
SUBMISSION.md           F3/D2 architecture for judges
```

## License / notes

Prototype for ET AI Hackathon (Accenture Agentic Edition), Problem 2. Do not commit API keys.
