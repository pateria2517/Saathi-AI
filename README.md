# SAATHI AI — PF & ESIC multilingual assistant

This release upgrades the existing Saathi AI HTML application while retaining its dark visual identity, question cards, response-language selector, English question entry for internal testing, translation toggle, HR ticket modals and ticket tracker.

## Scope and languages

- The assistant accepts only PF / EPF / EPFO / UAN and ESIC / ESI questions.
- User-facing answer languages are Hindi (`hi`), Kannada (`kn`) and Tamil (`ta`).
- English remains the development/testing input language and optional translation aid; it is not an answer-language choice.
- Questions outside PF and ESIC are declined before retrieval/generation.

## What is implemented

- FastAPI backend serving the existing `saathi_ai_trained.html` page.
- 710-row source knowledge pack retained. The answer index filters this to 614 PF/ESIC-related records.
- Retrieval-first answers from the uploaded multilingual FAQ records.
- Optional semantic vector retrieval using an OpenAI-compatible embeddings endpoint; lexical retrieval remains the offline fallback.
- LLM provider adapter for OpenAI-compatible endpoints, Anthropic Claude and Google Gemini. The model receives only retrieved PF/ESIC evidence and must abstain if it is insufficient.
- Optional MCP Streamable HTTP client for read-only policy/knowledge search tools. The LLM can select a permitted read-only search tool when an LLM and MCP server are configured. No MCP server is assumed to exist.
- Optional OpenAI text-to-speech for Hindi, Kannada and Tamil. The browser's installed speech voices are the fallback.
- Speech is only triggered for the final answer. It is split at punctuation, spoken more slowly, and given additional pauses after commas, semicolons, colons and sentence-ending punctuation.
- HR ticket creation requires explicit employee consent. A detected PF/ESIC issue prompts the user; it does not silently create a ticket. Employees can also create a PF/ESIC ticket manually, track it, close it and reopen it.
- SQLite local ticket storage. If an MCP server exposes an appropriate create-ticket tool, Saathi attempts to route the ticket there after consent; otherwise it is clearly labelled local-demo-only.
- Document ingestion for PDF, DOCX, TXT, Markdown, HTML, JSON, CSV and XLSX. Uploaded documents remain excluded from answer retrieval until an authorised reviewer marks them reviewed.
- API timeouts, input validation, request-size limits, no API secrets in frontend code, and tests for scope gating, language output, retrieval, follow-up context and ticket consent/status.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

Run tests:

```bash
# Run complete test suite (API, Payslip, MCP, Telephony, HTML/JS)
python -m pytest -v

# Run individual verification suites:
python -m pytest -v test_index_html.py    # Extracts <script> blocks, runs node --check, verifies all JS IDs in HTML
python -m pytest -v test_payslip.py       # Payslip line breakdown, statutory ceilings, remittance grace, continuous ESIC
python -m pytest -v test_mcp.py           # Model Context Protocol (7 tools, consent gate, tool logging)
python -m pytest -v test_saathi.py        # Core API, scope gating, telephony simulator, and Indic speech tests
```

## Configure a real LLM

The supplied environment intentionally defaults to `LLM_PROVIDER=none` because no API credentials were provided. In that mode, the application is fully usable as a grounded FAQ retrieval demo, but it does not call a generative LLM.

Open `.env` and choose one provider:

### OpenAI / OpenAI-compatible

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=YOUR_SECRET_KEY
LLM_BASE_URL=https://api.openai.com/v1
```

### Anthropic Claude

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=YOUR_CLAUDE_MODEL_ID
ANTHROPIC_API_KEY=YOUR_SECRET_KEY
```

### Google Gemini

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=YOUR_GEMINI_MODEL_ID
GEMINI_API_KEY=YOUR_SECRET_KEY
```

Restart the server after changing `.env`. Never paste a real API key into the HTML, browser console, or a public repository.

## Enable semantic embeddings

The code supports an OpenAI-compatible `/embeddings` endpoint. Configure:

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=YOUR_SECRET_KEY
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

Then build vectors for the 710 FAQ records:

```bash
python ingest.py --embed-faqs
```

The app uses hybrid lexical + vector retrieval when these vectors are available. Without embedding credentials, it uses its lexical/intent fallback and reports the configured mode accurately.

## Add company policy documents

Supported formats: PDF, DOCX, TXT, Markdown, HTML, JSON, CSV and XLSX.

1. Set a strong `ADMIN_TOKEN` in `.env`.
2. Upload documents to `POST /api/admin/ingest` using a multipart form field named `files` and an `Authorization: Bearer <ADMIN_TOKEN>` header.
3. New chunks are marked `pending_review` and are not used for answers.
4. An authorised policy owner must review the material. For a local reviewed import, run:

```bash
python ingest.py --reviewed path/to/approved_pf_esic_policy.pdf
```

This flag is an administrative assertion, not independent legal verification. Keep the original document and its effective date/revision record. The ingestion script extracts URLs only when they are actually present in the document; it never invents source links.

## Model Context Protocol (MCP) Architecture (Step 4)

Saathi AI natively implements the Model Context Protocol (MCP standard 2024-11-05). All external statutory queries, payslip breakdowns, compliance auditing, procedure how-tos, ticket management, and payroll checks execute through MCP tools by default across the API and telephony channels.

### 1. Seven Exposed MCP Tools
The MCP server (`saathi_mcp.py`) registers 7 tools with strict JSON Schemas:

| Tool Name | Type | Access Level | Description |
|---|---|---|---|
| `search_policy` | Query | Read-Only | Multilingual search across 710 canonical FAQs with Indic normalization and intent boosting. |
| `explain_payslip` | Computation | Read-Only | Line-by-line earnings and statutory deductions breakdown (Basic, Gross, Net Take-Home, PF, ESIC). |
| `check_payslip_anomalies` | Audit Engine | Read-Only | Deterministic statutory compliance audit checking remittance due dates (15th + grace period), wage ceilings, and employer matching. |
| `get_pf_howto` | Knowledge | Read-Only | Step-by-step guidance for passbook balance, UAN activation, online claims (Form 19/31), and job transfers. Includes official honesty notice that EPFO has no public balance API. |
| `get_worker_payroll_record` | HRMS Lookup | Read-Only | Retrieves Lakshmi's mock payroll record (`EMP-LAKSHMI-001`) from simulated warehouse HRMS. Clearly marked MOCK. |
| `get_ticket_status` | Query | Read-Only | Looks up status and history of an existing HR ticket by ID in local SQLite storage. |
| `create_hr_ticket` | State-Modifying | Consent-Gated | Creates an HR follow-up ticket. Strictly enforces `consent_given=True` as a required parameter; rejects unauthorized calls with `CONSENT_REQUIRED`. |

### 2. Execution Modes
- **In-Process Dispatch (Default Offline Mode)**: Zero-latency execution without external process overhead or network dependency.
- **Standard Stdio JSON-RPC 2.0**: Run `python saathi_mcp.py` as a standalone MCP server for Claude Desktop, Cursor, Antigravity, or other MCP hosts.
- **Streamable HTTP Client**: Connects to remote enterprise MCP endpoints when `MCP_SERVER_URL` and `MCP_AUTH_TOKEN` are configured in `.env`.

### 3. Tool Call Audit Logging
Every `/api/ask` and telephony turn records an audit trace of dispatched MCP tools (`mcp_tool_calls` list with tool name, arguments, status, and output summary), visible directly in the UI answer card.

### 4. EPFO API Transparency Notice
EPFO does not provide any public or external API for checking member balances. Neither Saathi AI nor any third-party app can directly access a worker's EPF account without active credentials. `get_pf_howto` transparently routes users to legitimate self-service methods (UMANG App, missed call to 9966044425, SMS `EPFOHO UAN` to 7738299899, or the official Member Passbook Portal).

## Payslip Parser & OCR Fallback (Step 2)

- **Digital PDFs**: Parsed directly in-memory using `pypdf` without saving any files to disk.
- **Scanned Images (.png, .jpg, .jpeg)**: Because cloud/Tesseract OCR dependencies are optional, uploading an image without Tesseract installed returns status `ocr_not_installed` with clear instructions:
  - Install Python libraries: `pip install pytesseract pillow pdf2image`
  - Install Tesseract OCR engine: download installer from GitHub (`UB-Mannheim/tesseract/wiki`) or via package manager (`winget install UB-Mannheim.TesseractOCR`).
  - Manual field entry is always recommended as the primary, 100% reliable input method.

## Voice

- Browser voice is enabled by default and uses the device's installed Hindi (`hi-IN`), Kannada (`kn-IN`) or Tamil (`ta-IN`) speech voice if available.
- Browser voice rate is set to `0.68`, with pauses inserted around punctuation. Device voice availability varies by browser/OS.
- For more consistent generated speech, configure:

```dotenv
TTS_PROVIDER=openai
TTS_API_KEY=YOUR_SECRET_KEY
TTS_BASE_URL=https://api.openai.com/v1
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=coral
```

The backend synthesises the actual answer text in the selected language at a slower speed and the frontend inserts sentence/punctuation pauses between audio segments. This uses a licensed speech-generation API rather than copying voice samples from random websites. If cloud TTS is unavailable, browser speech synthesis is used.

## Voice & Telephony Layer (Step 1)

Saathi AI supports phone-call accessibility for factory and warehouse workers through a dual telephony architecture:

1. **Production-Ready Webhook Interface**:
   - `POST /api/telephony/incoming` — Answers incoming call, serves initial language IVR menu (1: Hindi, 2: Kannada, 3: Tamil). Emits standard Twilio TwiML `<Gather>` or Exotel JSON.
   - `POST /api/telephony/language` — Gathers caller keypad digit or voice choice, switches session language to Kannada, Hindi or Tamil, and speaks welcome benefits prompt.
   - `POST /api/telephony/gather` — Gathers caller speech input, queries the benefits knowledge pipeline, and responds with slow-paced speech. Handles voice control commands:
     - **Repeat** ("ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ", "दोबारा बोलो", "repeat"): repeats the last explanation.
     - **Slower** ("ನಿಧಾನವಾಗಿ ಮಾತನಾಡಿ", "धीरे बोलो", "slower"): decreases speech rate (down to 0.65x) with natural punctuation pauses for low-literacy clarity.
     - **Talk to Human** ("ಮೇಲ್ವಿಚಾರಕ", "ಮಾನವ ಸಹಾಯ", "बात करनी है", "human"): flags call for human escalation, marks session as `HUMAN_ESCALATED`, and asks for consent to create an HR ticket.

2. **Interactive Browser Call Simulator**:
   - Accessible via the **"📞 Open Phone Call Simulator"** button or the **"👤 1-Click Demo: Lakshmi's Call (Kannada)"** button in the web UI.
   - Connects to `POST /api/telephony/simulate` and runs 100% offline without requiring paid telephony credits or phone numbers.
   - Uses the browser's Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`) for speech input in `kn-IN`, `hi-IN`, or `ta-IN`, and `speechSynthesis` for slower paced voice output with conversational pauses.
   - Includes quick spoken prompt chips and keypad buttons for reliable testing even if microphone access is denied.

> **Important Note on Telephony Provider Indic STT Support**:
> External telephony platforms (such as Twilio, Exotel, or Plivo) have varying acoustic model availability and streaming speech-to-text capabilities for Indian regional languages. Do not assume built-in support for Kannada (`kn-IN`), Hindi (`hi-IN`), or Tamil (`ta-IN`). Always verify language recognition accuracy and audio stream codec compatibility with your chosen telephony vendor, or bridge the raw call audio via Media Streams / WebSockets to an Indic-specialized ASR engine (e.g. Google Cloud Speech-to-Text or Bhashini).

## Accuracy and ticket behaviour

- `MIN_RETRIEVAL_SCORE=0.80` is an evidence-retrieval gate, not a probability that the answer is factually correct.
- The UI labels the percentage as **evidence match / retrieval relevance**, never factual accuracy.
- Below the threshold, Saathi declines to generate an answer from weak evidence and asks the user to rephrase or contact HR.
- Above the threshold, an answer may be returned only when PF/ESIC evidence is retrieved.
- A suspected discrepancy can show a ticket prompt. The employee must explicitly consent before any ticket is created. This preserves the project safety requirement and avoids silently creating HR cases.

## Important production limitations

This package contains no live API credentials, MCP server URL, employer ticketing destination, payroll credentials or employee identity provider. Therefore:

- LLM, embeddings, cloud TTS and MCP integrations are implemented as configurable adapters but are **not live-connected** until the organisation supplies valid credentials/endpoints.
- The default no-key mode uses the uploaded FAQ knowledge pack; it is not a fine-tuned model.
- The 710 FAQ records do not include authoritative source URLs, policy section numbers or verification dates. They are labelled as uploaded FAQ material and should be reviewed by HR/legal subject-matter owners before employee use.
- Ticket storage is local SQLite unless an authorised MCP create-ticket tool is configured. Local tickets are not sent to HR.
- Employee-specific PF/ESIC records are not available in this demo and must not be inferred or fabricated.
- Browser voice depends on installed system voices. Use configured cloud TTS for a more consistent voice experience across devices.

## Included source files

- `knowledge_base.json` — combined 710 FAQ records used by the backend.
- `Saathi_AI_new_600_faq_only.json` — uploaded 600-record source file.
- `Saathi_AI_FAQ_Training_Pack.xlsx` — original training workbook.
- `Saathi_AI_updated_710records.html` — supplied updated HTML/FAQ source.
- `saathi_ai_110_qa.csv` — original 110-record CSV.
- `original_saathi_ui_foundation.html` — existing UI foundation preserved in the delivered page.
- `saathi_ai_trained.html` — updated frontend.

The dataset is loaded as retrieval knowledge. This is not model fine-tuning.
