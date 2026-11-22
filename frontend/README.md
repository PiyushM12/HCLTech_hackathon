# SchemeSathi — web frontend

Citizen-facing web app for SchemeSathi, the multilingual welfare-scheme assistant for the
fictional state of Mitrapur Pradesh. Vite + React 18 + TypeScript, plain CSS, `lucide-react` icons.

## Run it

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server proxies `/api/*` to the FastAPI backend at `http://localhost:8000`, stripping the
`/api` prefix (`/api/ask` → `http://localhost:8000/ask`). Start the backend first. To point the
proxy elsewhere:

```bash
API_PROXY_TARGET=http://localhost:8001 npm run dev
```

To call an API directly instead of through the proxy, set `VITE_API_BASE` at build/dev time
(the backend then needs CORS for the UI origin):

```bash
VITE_API_BASE=http://localhost:8000 npm run dev
```

Other scripts:

| Command             | What it does                                 |
| ------------------- | -------------------------------------------- |
| `npm run build`     | Type-checks (`tsc --noEmit`) and builds `dist/` |
| `npm run preview`   | Serves the production build on port 4173     |
| `npm run typecheck` | Type-check only                              |

## Docker

`Dockerfile` is a two-stage build (Node 22 → `nginx:alpine`). `nginx.conf` serves the SPA and
proxies `/api/` to `http://api:8000/` (prefix stripped) with `client_max_body_size 20m` for uploads.
In docker compose, name the backend service `api`:

```yaml
  ui:
    build: ./frontend
    ports: ["8080:80"]
    depends_on: [api]
```

## What's in the app

| Tab                   | Purpose |
| --------------------- | ------- |
| **Ask** (default)     | Chat with the assistant. Answers show an answer-type badge, eligibility cards with a rule-by-rule table, clarification questions with quick replies, citation chips that open the cited section of the source, confirm/cancel cards for proposed actions (with expiry countdown), referral cards with the handoff bundle, and a "Why this answer?" audit drawer. |
| **Check eligibility** | Form that calls the deterministic rule engine (`POST /eligibility`) directly; results grouped by verdict. |
| **Schemes**           | All schemes with status and last date for the selected as-of date, required documents, and "Ask about this scheme". |
| **Sources**           | Searchable, filterable Source Register; any row opens the document. |
| **Admin**             | Health of API / SQLite / vector store / LLM, document ingest, CSV test-data loader. |

Top bar: language selector (Auto-detect, हिन्दी, English, ಕನ್ನಡ, தமிழ்), identity picker (Guest or a
demo citizen from `/citizens/demo`, with consent status) and an **Advanced** popover holding the
`as_of_date` used to test dates and deadlines.

- The selected language is sent as `language` on `/ask` and also translates the UI chrome
  (`src/i18n.ts`). Auto-detect omits `language` and uses English chrome.
- The conversation (messages, `conversation_id`), identity, language and as-of date are kept in
  `localStorage`, so a refresh keeps the chat. Switching identity starts a new conversation.
- Fonts: Noto Sans + Noto Sans Devanagari/Kannada/Tamil from Google Fonts, with system fallbacks
  (Nirmala UI, Mangal, Tunga, Latha, …) so Indic text still renders offline.
- Layout works down to 360 px (bottom tab bar, bottom-sheet drawers), supports dark mode and
  respects `prefers-reduced-motion`.

## Code map

```
src/
  api.ts            typed fetch client (X-Citizen-Id header, {detail} errors → ApiError)
  types.ts          TypeScript mirror of backend/app/models.py + other endpoint shapes
  i18n.ts           UI strings in en / hi / kn / ta
  styles.css        design tokens (CSS custom properties) and all styles
  state/
    session.tsx     identity, language, as-of date, conversation (reducer + localStorage)
    chat.tsx        send / retry / confirm / cancel
    ui.tsx          current tab (URL hash), open drawer, composer pre-fill
  components/       AppShell, TopBar, ChatView, MessageCard, EligibilityCard, ActionCard,
                    ReferralCard, CitationChips, QuestionsBlock, Composer, SourceDrawer,
                    AuditDrawer, ReferralDrawer, Markdown, JsonView, …
  pages/            AskPage, EligibilityPage, SchemesPage, SourcesPage, AdminPage
  lib/              formatting, attribute labels, localStorage wrapper, useAsync
```

## API assumptions

Where the contract left room, the UI assumes the following (all degrade gracefully if not true):

- `SchemeVerdict.scheme_names` is keyed by language code (`en`, `hi`, `kn`, `ta`); `name_<lang>` keys also work.
- Cited sections are found by number in Markdown headings (`## 3 Eligibility`, `### 3.4 …`). If the
  exact number is missing the parent section is used, then a title match; otherwise the whole
  document is shown with a note.
- A source whose `content` starts with `{` or `[` is treated as JSON (grievances) and shown as fields.
- `AskResponse.referral` and the `GET /referrals/{id}` bundle follow Annex D (`queue`, `priority`,
  `referral_reasons`, `citizen_summary`, `evidence` items with `source_id`/`section` or
  `tool`/`output`, `attempted_answer`, `unresolved_questions`, `pii_redacted`). Unknown keys are still shown.
- The audit record and health component details are free-form objects, rendered generically.
- Confirm/cancel are sent with an empty JSON body. 409 is shown as "already handled", 410 as
  "expired", 403 as "only the person who asked can confirm", 404 as "no longer exists".
- `as_of_date` is sent only when the user changes it in Advanced (the backend defaults to today).
- Quick-reply chips send short English phrases ("Female", "Rural, I live in a village"). In
  Auto-detect mode they pin `language` to the previous answer's language so the reply language
  doesn't switch to English.
- `/citizens/demo` is called as `guest`.
- `GET /conversations/{id}` is in the client but the chat history is kept locally rather than re-fetched.
