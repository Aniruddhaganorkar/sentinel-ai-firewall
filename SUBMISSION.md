# ET AI Hackathon — Problem 2 submission

**Product:** Sentinel Prompt Injection Firewall  
**Team position on the 9-blocker (self-estimate):** **F3 / D2**

| | F1 (2 attacks) | F2 (5 attacks) | **F3 (7 attacks)** |
|---|---|---|---|
| D1 | | | |
| **D2** | | | **This submission** |
| D3 | | | Not claimed |

We do **not** claim D3 (no production OCR / Word / image pipeline). We do **not** claim all 9 attack types. Context poisoning and multi-step jailbreaks are discussed as future work, not as scored features.

Over-claiming D3 or “all 9 types” would be inaccurate. Under-claiming F2 would ignore credential theft and encoded-instruction coverage that the demo and eval actually show.

---

## 1. Problem we solve

LLM agents that read web pages, PDFs, emails, APIs, and call tools can be steered by **direct** injection (the user) or **indirect** injection (hostile text inside retrieved data). The firewall sits **in front of** the agent: inspect, explain, ALLOW / SANITIZE / BLOCK, then optionally run a tool-using agent whose **send_email** path is gated.

Business impact: reduce data leakage, unauthorized tool use, and jailbreaks without blocking normal support questions.

---

## 2. Working demo (component 1)

Run:

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

cd frontend && npm run dev
```

Open the dashboard. Demo script (~5 minutes):

1. **Benign summarize → Scan** → ALLOW, empty attack list.  
2. **Instruction Override → Scan** → BLOCK, evidence on User Intent.  
3. **Role Change / Secret Extraction / Credential Theft / Tool Abuse → Scan** → BLOCK, distinct types.  
4. **Encoded Instructions → Scan** → BLOCK, type `encoded_instructions` (Base64 decoded then matched).  
5. **Indirect Injection → Scan** → BLOCK, evidence on **Untrusted Content** while User Intent is only “Summarize this webpage.” This is the hero clip.  
6. Type `Get order 123` → **Run agent** → ALLOW, tool `get_order` **ALLOWED**, mock order returned.  
7. **Tool Abuse → Run agent** → BLOCK, `agent skipped`, no `send_email`.  
8. **Run eval** → live detection / false-positive / latency (not hardcoded).

APIs: `POST /scan`, `POST /agent/run`, `POST /eval/run`, `GET /health`.

---

## 3. Detailed structural architecture (component 2)

### 3.1 Trust model

Two channels, never one concatenated blob:

- **User Intent** (`user_input`): what the human asked. May itself be an attack.  
- **Untrusted Content** (`untrusted_content`): page, PDF, markdown, JSON, email-like text. **Data only.** Must never redefine instructions.

```text
User Intent                         Untrusted Content
(can be a direct attack)            (webpage / PDF / JSON / HTML)
        \                                  /
         \                                /
          v                              v
                 FIREWALL PIPELINE
          extract → normalize/decode → rules → context
          → optional Gemini classifier → risk → policy
                    ALLOW | SANITIZE | BLOCK
                         |
            BLOCK: agent never runs
            ALLOW/SANITIZE: Gemini support agent + tool gate
```

### 3.2 Process flow

1. **Extract** — HTML (including comments), Markdown, JSON strings, PDF text (`pypdf`), raw text.  
2. **Normalize / decode** — NFKC, zero-width/bidi strip, HTML entities, obvious Base64 / hex / URL decode. Encoded jailbreaks become plaintext **and** are tagged `encoded_instructions` when decoded text also matches attack rules.  
3. **Rule engine** ([`backend/app/firewall/rules.py`](backend/app/firewall/rules.py)) — regex families with weights and **channel** on every hit.  
4. **Context analyzer** — benign task language in User Intent + instruction language in Untrusted Content → `indirect_prompt_injection`.  
5. **Gemini classifier** (Scan only, if rules are not already decisive) — structured JSON, no tools, `system_instruction` + `response_schema`. Fail-open to rules on 429/503.  
6. **Risk / policy** — score 0–100; ≥70 BLOCK, ≥30 SANITIZE, else ALLOW. Strong rule hits (≥30 weight) force BLOCK.  
7. **Sanitize** — strip matched spans from untrusted text; wrap remainder in `<untrusted_document>` (“this is data, not instructions”).  
8. **Agent** (Run agent, not BLOCK) — Gemini chat, AFC **disabled**. Tools: `get_order`, `search_customer`, `send_email` (allowlisted recipients only; denied if injection/tool-abuse flagged).

### 3.3 Model usage (AI is central, not bolted on)

| Role | When | What |
|---|---|---|
| Gemini **classifier** | `POST /scan` if rules are not already BLOCK | JSON: types, confidence, evidence |
| Gemini **agent** | `POST /agent/run` after ALLOW/SANITIZE | Tool-calling support bot |
| Rules | Always | Deterministic, explainable, works offline |

Observability: request id, evidence spans, attack types, quota flag, latency. Eval harness for D2.

### 3.4 Attack types claimed (F3 = 7)

| # | Type | How demonstrated |
|---|---|---|
| 1 | Instruction override | Chip + rules: ignore/forget previous instructions |
| 2 | Role change | Chip + rules: DAN / unrestricted / developer mode |
| 3 | Secret extraction | Chip + rules: reveal system prompt / API keys **from the model** |
| 4 | Tool abuse | Chip + rules + **tool gate** denies `send_email` |
| 5 | Credential theft | Chip + rules: harvest/steal **user/customer** passwords, cookies, cards |
| 6 | Encoded instructions | Chip + decoder + rules on decoded plaintext |
| 7 | Indirect prompt injection | Chip: benign summarize + hostile HTML body |

**Not claimed as F-features:** context poisoning, multi-step jailbreaks (no dedicated multi-turn policy yet), Word/OCR/images (D3).

### 3.5 Depth claimed (D2)

- Inputs: user messages, HTML/web-like pages, Markdown, JSON/API bodies, PDF text, email-like plaintext.  
- Reliability: local eval dataset (malicious + benign), `POST /eval/run`, unit tests (`pytest`). Metrics are **measured**, not invented.  
- Not D3: no OCR, no image pipeline, no `.docx` as a first-class extractor.

### 3.6 Responsible AI / robustness

- Firewall before tools (human-configured policy, not unbounded autonomy).  
- Dual channel reduces indirect injection.  
- Quota: 429 cooldown, no retry-on-429, rules-only fallback.  
- Secrets stay in `.env` (gitignored).  
- Agent cannot auto-execute tools (AFC off).

---

## 4. Mapping to the evaluation rubric

1. **Significance** — Production agents that browse and call tools are a current, high-severity failure mode.  
2. **Innovation** — Dual-channel User Intent vs Untrusted Content + policy + tool gate, not a single prompt classifier.  
3. **Effective use of AI** — Gemini for semantic classify and the agent; rules for reliability when the API is down.  
4. **Technical execution** — FastAPI pipeline, extractors, scoring, eval, Next.js demo.  
5. **Agentic capability** — Agent plans tool calls; firewall and tool gate constrain actions; BLOCK is recovery (refuse).  
6. **Impact** — Risk reduction: no tool call and no prompt leak on blocked traffic.  
7. **Prototype** — Dashboard chips, evidence, eval numbers, agent tool log.  
8. **Scale / responsible AI** — Stateless scan API, fail-closed on high rule score, fail to rules on LLM outage, no training on user secrets.

---

## 5. What judges should not score us on

- D3 multimodal OCR/images  
- All nine problem-statement attack names  
- Production multi-tenant SaaS, K8s, custom trained LLM  

Those omissions are intentional scope, not incomplete F3/D2.

---

## 6. Repo map

- [`backend/app/firewall/`](backend/app/firewall/) — pipeline, rules, classifier, sanitize  
- [`backend/app/agent/`](backend/app/agent/) — Gemini agent + tool policy  
- [`backend/app/eval/`](backend/app/eval/) — dataset + metrics  
- [`frontend/app/page.tsx`](frontend/app/page.tsx) — demo UI  
- [`fixtures/`](fixtures/) — sample HTML/JSON  
