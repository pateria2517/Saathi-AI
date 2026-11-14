# Saathi AI — 710-FAQ Local Demonstration

This release keeps the existing dark Saathi AI page and upgrades its knowledge data and demo workflows. It includes the original first-page design, the reconciled 710-record multilingual FAQ pack, a small Python backend, and a local SQLite ticket queue.

## What was loaded from the four supplied knowledge sources

| Input | Use in this release |
|---|---|
| `Saathi_AI_new_600_faq_only.json` | Added 600 records (SAH-111 to SAH-710) |
| `Saathi_AI_combined_710_faq.json` | Canonical combined 710-record FAQ list |
| `Saathi_AI_FAQ_Training_Pack.xlsx` | Validated the `All 710 QA` and `New 600 Only` sheets and workbook summary |
| `Saathi_AI_updated_710records.html` | Cross-checked its embedded FAQ block against the combined JSON |
| `saathi_ai_enhanced(1).html` | Used as the original page/UI foundation; its layout and branding were preserved |

The workbook summary describes 110 original + 600 new rows, 50 topics/intents, and 12 question phrasings per new topic. It also notes that new Hindi, Kannada and Tamil answers were machine-translated and should receive native-speaker review. The updated 710-record HTML and the combined JSON have matching embedded FAQ data. The 600-only JSON corresponds to the last 600 records in the combined dataset.

## Features in this release

- 710 FAQ records loaded into both the browser page and backend knowledge index.
- English-only question entry for development/testing, with answers in Hindi, Kannada or Tamil.
- Four-language introduction tabs remain available as requested earlier; English is not an answer-language choice.
- Optional English translation of the answer.
- FAQ exact matching, intent rules, weighted lexical retrieval and single-edit spelling correction.
- 80% acceptance threshold; below threshold the assistant displays a language-specific “I couldn't understand the question” response.
- Browser speech synthesis at a slower rate (0.72) with punctuation-based pauses.
- Request-HR-ticket prompt for potentially incorrect or sensitive issues; the employee must grant consent.
- Manual employee-created ticket form with required consent.
- Ticket tracker with Open/Closed status and close/reopen controls.
- Local SQLite ticket persistence when using the Python server; browser localStorage fallback when the HTML is opened directly.
- HTML input size and backend validation limits; ticket creation requires `consent: true`.

## Run locally

Requires Python 3.10+ and no third-party packages.

1. Extract this release ZIP into a folder.
2. Open a terminal in that folder.
3. Run:

   ```bash
   python saathi_ai_server.py
   ```

4. Open `http://127.0.0.1:8000` in a browser.

The server binds to `127.0.0.1` by default. To use a different local port:

```bash
python saathi_ai_server.py --port 8765
```

Opening `saathi_ai_trained.html` directly also runs the local FAQ-matching front end and keeps demo tickets in that browser's localStorage. To use the server-side SQLite ticket tracker, serve the page through the Python server.

## Backend endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Serves the Saathi AI page |
| GET | `/api/health` | Health check and FAQ count |
| GET | `/api/knowledge-base` | Knowledge-base metadata |
| POST | `/api/ask` | Retrieves a FAQ answer in `hi`, `kn` or `ta` |
| GET | `/api/tickets` | Lists local demonstration tickets |
| POST | `/api/tickets` | Creates a ticket only with explicit `consent: true` |
| PATCH | `/api/tickets/{id}` | Sets ticket status to `Open` or `Closed` |

Example `/api/ask` request:

```json
{
  "question": "My PF claim was rejected. What should I do next?",
  "language": "kn"
}
```

## Important capability boundaries

This is a working **retrieval-based demonstration**, not model fine-tuning and not a production agent. The system returns stored multilingual FAQ answers selected by retrieval and intent rules. It does not connect to an external LLM, generate novel policy interpretations, create embeddings, or use a vector database. A similarity/retrieval score is used internally for the 0.80 gate and is not displayed as factual accuracy.

The included ticket service creates and tracks records in a local SQLite demo queue. It does **not** notify a real HR team or connect to an organisation's ticketing system. There is no employee authentication, role-based access, identity verification, or live payroll/EPFO/ESIC access. Do not place real employee personal data into this local demonstration.

The current files do not contain official source URLs, policy section identifiers, or verification dates for each answer. Those metadata fields are left blank/unverified rather than fabricated. General PF/ESIC claims and company policy details must be checked against current official guidance and organisation-approved documents before deployment. The 600 added Hindi/Kannada/Tamil translations need native-speaker review.

Voice playback relies on the browser/operating system's installed speech voices. The selected language may not have a voice installed on every device; text answers remain available. Actual pronunciation and voice quality must be checked on the target phones.

## Before production deployment

- Add an authenticated backend, RBAC, HTTPS, secure database, audit trail, retention controls and rate limiting.
- Connect a server-side LLM and embeddings provider only after selecting an approved vendor; keep keys in server environment variables, never in the HTML.
- Index current official EPFO/ESIC documents and company-approved HR/payroll policies, with source URL, policy section, effective date, verification date and review status.
- Connect MCP/HR tools only through authenticated, permission-scoped endpoints; verify the employee and consent before reading an employee's own record or creating a real ticket.
- Add a human-owned HR ticket destination and escalation SLA; the current queue is local demo-only.
- Have qualified HR/legal reviewers and native Hindi/Kannada/Tamil speakers approve the data before employee use.

## Configuration template

`.env.example` lists reserved placeholders for future integrations. The current local demo does not read these variables and contains no API credentials.
