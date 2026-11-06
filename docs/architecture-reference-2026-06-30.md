> **Relocated 2026-11-05.** This is the architecture reference that lived at `CLAUDE.md`
> from 2026-06-30, moved here unchanged (apart from this note) when `CLAUDE.md` was
> rewritten as a short operating guide. It is accurate on the architecture as of commit
> `a685431`. Its §13 (TOMIC portability) is partly superseded by §5 of
> [`syvrona-modernization-and-value-assessment-2026-11-05.md`](syvrona-modernization-and-value-assessment-2026-11-05.md).

# CLAUDE.md — Syvrona AI Architecture Reference

> Generated: 2026-06-30  
> Repo: `syvrona-ai`  
> Purpose: Authoritative architecture reference for Claude and human engineers. Includes a dedicated TOMIC portability assessment at the end.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack & Dependencies](#2-tech-stack--dependencies)
3. [Entry Points & Deployment](#3-entry-points--deployment)
4. [Directory Structure](#4-directory-structure)
5. [Core Architecture Patterns](#5-core-architecture-patterns)
6. [Data Flow](#6-data-flow)
7. [Real-Time Streaming](#7-real-time-streaming)
8. [Config & Registry Patterns](#8-config--registry-patterns)
9. [Rate Limiting & Quota Enforcement](#9-rate-limiting--quota-enforcement)
10. [Database Schema](#10-database-schema)
11. [Key Conventions](#11-key-conventions)
12. [AI/LLM Integration — Deep Dive](#12-aillm-integration--deep-dive)
13. [AI Assistance — Portability to TOMIC](#13-ai-assistance--portability-to-tomic)

---

## 1. Overview

Syvrona is a multi-provider AI chat SaaS built on Flask. Users authenticate, subscribe via Stripe, and interact with OpenAI, Anthropic Claude, and Google Gemini models through a single streaming chat interface. Conversations, prompts, and prompt-chains are persisted in MySQL. Rate limiting and token quotas enforce plan-tier constraints.

---

## 2. Tech Stack & Dependencies

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask 3.1.2 |
| ORM | SQLAlchemy 2.0 + Flask-SQLAlchemy + Flask-Migrate (Alembic) |
| Database | MySQL 8.0 (production), SQLite in-memory (tests) |
| Rate limiting | Flask-Limiter 4.0 backed by Redis 8 |
| Auth | Flask-Login 0.6.3, Werkzeug password hashing, itsdangerous tokens |
| CSRF | Flask-WTF 1.2.2 |
| Captcha | flask-hcaptcha |
| AI providers | `openai==2.8.1`, `anthropic==0.73.0`, `google-genai==1.51.0` |
| Tokenization | `tiktoken==0.12.0` (cached via `lru_cache`) |
| Billing | Stripe 13.2 |
| Email | Mailgun (via `app/utils.py`) |
| Markdown rendering (client) | `marked.min.js` (bundled static) |
| WSGI server | Gunicorn 23 (`gthread` worker class) |
| Container | Docker + Docker Compose |
| CI | GitHub Actions (pytest via Docker, python-lint, release-drafter) |

---

## 3. Entry Points & Deployment

### Local / development
```
python app.py   # host/port from FLASK_RUN_HOST / FLASK_RUN_PORT
flask run       # via .flaskenv: FLASK_APP=app.py
```

### Production
```
gunicorn -c app/gunicorn.conf.py "app:create_app()"
```
`app/gunicorn.conf.py` key settings:
- `worker_class = "gthread"` — I/O-bound streaming friendly
- `workers = int(os.getenv("GUNICORN_WORKERS", 5))`
- `threads = int(os.getenv("GUNICORN_THREADS", 2))`
- `preload_app = False` — avoids forked DB connection sharing
- `worker_tmp_dir = "/dev/shm"` — RAM-backed heartbeat for container environments

### Docker Compose services
- `web` — Flask/Gunicorn app, port 5001→5000
- `mysql` — MySQL 8.0, persistent volume
- `redis` — Redis 8, ephemeral (no RDB/AOF), rate-limit store only
- `test` — same image, runs `pytest` with SQLite in-memory

### Config/env
`app/config.py` → `class Config` reads everything from environment. Hard failures at startup if `DATABASE_URL` or `SECRET_KEY` are missing. Three config classes: `Config`, `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`. The factory `create_app(config=None)` accepts an override dict (used in tests).

---

## 4. Directory Structure

```
app.py                      # WSGI entry point; calls create_app()
app/
  __init__.py               # Application factory: create_app(), Blueprint registration
  config.py                 # Config class (all env vars, DB pool, rate limits, feature flags)
  constants.py              # PRICE_LABELS, STRIPE_SUBSCRIPTION_STATUSES
  decorators.py             # @require_active_subscription, @admin_required
  extensions.py             # Redis singleton, Flask-Limiter singleton, init_extensions()
  feature_flags.py          # is_feature_enabled() / get_feature_config()
  limits.py                 # plan_limits(), enforce_token_quota decorator
  log_config.py             # configure_logging() — stdout, LOG_LEVEL env var
  model_limits.py           # get_max_tokens() helper
  model_registry.py         # MODEL_REGISTRY dict, PROFILE_OVERRIDES, build_generation_config()
  models.py                 # All SQLAlchemy models + helper CRUD functions
  ratelimit_logging.py      # 429 error handler blueprint
  tokenizer.py              # get_tokenizer(model) — tiktoken, lru_cache
  auth.py                   # /login /signup /logout /reset-password blueprints
  billing.py                # /create-checkout-session, /webhook Stripe blueprints
  chain.py                  # /chains CRUD blueprint
  chat.py                   # /chat, /answer, /conversation/*, /messages/* blueprints
  health_routes.py          # /healthz, /readyz blueprints
  knowledge_base.py         # /knowledge_base/* blueprints
  prompt.py                 # /prompts CRUD blueprint
  routes.py                 # / index, /privacy, /terms, /sitemap.xml (main blueprint)
  support.py                # Ticket/support blueprint
  tags.py                   # /tags blueprint
  providers/
    base_provider.py        # AIProvider ABC: stream_response() abstract method
    anthropic_provider.py   # AnthropicProvider
    openai_provider.py      # OpenAIProvider + _EndpointStrategy + STRATEGY_REGISTRY
    gemini_provider.py      # GeminiProvider
  services/
    ai_streamer.py          # AIStreamer facade, ProviderRegistry, MessagePersister
    conversation.py         # Service-layer wrappers over models.py conversation fns
    signup.py               # SignupHandler (email + Stripe customer creation)
    tags.py                 # Tag service helpers
  static/js/
    marked.min.js           # Markdown renderer
    tags.js                 # SyvronaTags — client-side tag input/suggestion
    chain_create.js         # Drag-to-reorder prompt chains (Sortable.js)
    modal.js, taginput.js   # UI helpers
  templates/
    chat.html               # Primary chat UI (streaming JS logic inline)
    ...                     # Jinja2 templates for all routes
migrations/                 # Alembic migration versions
tests/
  test_app.py               # Pytest integration tests
  conftest.py               # App/client fixtures
```

---

## 5. Core Architecture Patterns

### Application factory
`create_app()` in `app/__init__.py` constructs and configures the Flask app, calls `init_extensions()`, registers all Blueprints, and sets up context processors and error handlers. `preload_app = False` in Gunicorn means each worker calls `create_app()` independently — this prevents connection-pool sharing across forked processes.

### Blueprint decomposition
Every feature domain is a Blueprint: `main`, `auth`, `admin`, `billing`, `health`, `chat`, `support`, `prompt`, `chain`, `knowledge_base`, `tags`, `ratelimit_logging`. This isolates route namespaces and allows independent testing.

### Provider abstraction
`AIProvider` (abstract base class in `app/providers/base_provider.py`) defines a single method:
```python
def stream_response(self, message, user_id, conversation_id, model, system_prompt=None) -> Generator[str, None, None]
```
Three concrete implementations: `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`. All are instantiated once per `ProviderRegistry` instance (which is instantiated once per `AIStreamer`, which is instantiated per request in `chat.py:/answer`).

### Endpoint strategy (OpenAI)
`OpenAIProvider` further delegates to `_EndpointStrategy` objects keyed by model, supporting `chat` (Chat Completions API) and `responses` (Responses API for O-series models). The `STRATEGY_REGISTRY` dict is built at module import time from `MODEL_REGISTRY`.

### Facade / service layer
`AIStreamer` in `app/services/ai_streamer.py` is the single call-site for all AI interactions. It orchestrates:
1. User message persistence
2. Token pre-counting
3. Provider dispatch + streaming
4. Assistant message persistence (only on successful stream completion)
5. Atomic monthly token counter upsert
6. Fallback model recursion on `ModelAccessError`

### Connection pool management
`app/config.py` configures SQLAlchemy with `pool_size=10`, `max_overflow=5`, `pool_pre_ping=True`, `pool_recycle=1800`, and `pool_reset_on_return="rollback"`. This is an explicit architectural decision to avoid MySQL `wait_timeout` disconnects under long-running Gunicorn workers.

### Singleton extensions
`app/extensions.py` holds a module-level `redis_client` and `limiter`. `init_extensions()` is idempotent (guarded by `app.extensions["limiter_init_done"]`), ensuring no double-init across test reloads.

---

## 6. Data Flow

### Chat request lifecycle
```
Browser (fetch POST /answer)
  → @limiter.limit(plan_limits)           # Flask-Limiter checks Redis
  → @login_required                       # Flask-Login session check
  → @require_active_subscription          # checks User.subscription_status
  → @enforce_token_quota                  # queries UsageStat, returns 402 if over
  → chat.py:answer()
      → create_conversation() if new      # inserts Conversation row
      → AIStreamer().chat(message, user_id, conversation_id, model)
          → get_model_metadata(model)     # reads MODEL_REGISTRY
          → ProviderRegistry.get_provider(key)
          → MessagePersister.save_user()  # commits Message(role='user')
          → provider.stream_response()    # calls LLM API, yields tokens
          → [stream tokens back to browser via Response(generate())]
          → MessagePersister.save_assistant()  # commits Message(role='assistant')
          → AIStreamer._inc_usage()       # upserts UsageStat (MySQL ON DUPLICATE KEY)
  → Response headers: X-Conversation-Id, X-CSRFToken (rotated)
```

### Conversation context assembly
Each provider fetches full conversation history from the database via `get_conversation_messages(conversation_id)` at stream time, building the message list to send to the LLM. No in-memory conversation cache exists — every request reads from MySQL.

---

## 7. Real-Time Streaming

### Server side
`chat.py:answer()` returns `Response(generate(), content_type="text/plain")` wrapped in `@stream_with_context`. The `generate()` inner function iterates the generator from `AIStreamer.chat()`, which in turn iterates the provider's `stream_response()` generator. Token chunks flow straight through without buffering.

### Client side (`app/templates/chat.html`, inline `<script>`)
```js
const response = await fetch("/answer", { method: "POST", ... });
const reader = response.body.getReader();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    output += new TextDecoder().decode(value);
    assistantMsgContent.innerHTML = marked.parse(output);  // incremental markdown render
}
```
A "Thinking…" spinner placeholder is injected immediately before the fetch; it is removed on first non-empty token. Markdown is re-parsed on every chunk (full accumulation, not diff).

### Error surface
The client handles HTTP 429 (rate limit), 402 (token quota), and generic non-OK responses by calling `setAssistantError()` to replace the spinner with an error bubble. No retry logic on the client.

### CSRF rotation
Each streaming response includes a fresh CSRF token in the `X-CSRFToken` response header, which the client applies to both the hidden form field and `window.csrf_token` so the next request is valid.

---

## 8. Config & Registry Patterns

### `MODEL_REGISTRY` (`app/model_registry.py`)
The central model configuration dict. Each entry:
```python
"claude-sonnet-4-5-20250929": {
    "provider": "anthropic",          # maps to ProviderRegistry key
    "display_name": "Claude 4.5 Sonnet",
    "max_tokens": 64000,
    "encoding": "cl100k_base",        # for tiktoken
    "system_prompt": "...",           # optional override
    "fallback_model": "...",          # optional; AIStreamer recurses on ModelAccessError
    "generation_config": {            # merged into provider call kwargs
        "temperature": 0.35,
        "top_p": 0.95,
    },
}
```
`DEFAULT_MODEL_KEY = "gpt-5.2-chat-latest"` sets the UI default.

`build_generation_config(model, profile, overrides)` supports three-layer merging: registry defaults → profile → per-call overrides. Profile presets (`"coding"`, `"creative"`, `"summarize"`, etc.) live in `PROFILE_OVERRIDES` but are not yet surfaced to users.

### `STRATEGY_REGISTRY` (`app/providers/openai_provider.py`)
Built at import time from `MODEL_REGISTRY`: maps OpenAI model keys to `_EndpointStrategy` instances (`"chat"` or `"responses"`). This isolates the different streaming extraction logic for Chat Completions vs. Responses API.

### `ProviderRegistry` (`app/services/ai_streamer.py`)
Maps provider keys (`"openai"`, `"anthropic"`, `"gemini"`) to provider singleton instances. Currently instantiated per `AIStreamer` construction, which happens per request.

### Feature flags (`app/feature_flags.py`)
Thin wrappers over `app.config["FEATURE_FLAGS"]`, which is a dict populated from env vars in `Config`. Currently: `FREE_TRIAL_ENABLED`, `FREE_TRIAL_DAYS`.

### Rate limit tiers (`app/config.py`)
`RATE_LIMIT_TIERS` is a JSON-parseable env var (defaulting to `{"free": "5 per minute;100 per day", "pro": "60 per minute;3000 per day"}`). `TOKEN_QUOTAS` is a similar JSON env var for token caps.

---

## 9. Rate Limiting & Quota Enforcement

Two independent enforcement layers stack on the `/answer` endpoint:

**Layer 1 — Request rate (Flask-Limiter + Redis)**
- `@limiter.limit(plan_limits)` — `plan_limits()` returns the tier string based on `User.subscription_plan` vs. `STRIPE_PRICE_IDS`.
- Key function: `_user_or_ip()` — user ID when authenticated, remote IP otherwise.
- Storage: Redis (avoids per-worker in-memory state drift across Gunicorn workers).
- 429 errors are caught by `ratelimit_logging.py`'s `@bp.app_errorhandler(RateLimitExceeded)` which logs and returns plain-text 429.

**Layer 2 — Monthly token quota (MySQL)**
- `@enforce_token_quota` (decorator in `app/limits.py`) reads `UsageStat` for current month and returns 402 if over `TOKEN_QUOTAS[tier]`.
- `AIStreamer._inc_usage()` atomically increments the counter via MySQL `INSERT ... ON DUPLICATE KEY UPDATE tokens = tokens + N` — safe under concurrent Gunicorn workers.

---

## 10. Database Schema

Key models in `app/models.py`:

| Model | Key fields | Notes |
|---|---|---|
| `User` | id, email, password, subscription_status, subscription_plan, stripe_customer_id, preferences (JSON) | Flask-Login UserMixin |
| `Conversation` | id, user_id (FK→User CASCADE), title, created_at | Auto-titled from first 60 chars of prompt |
| `Message` | id, conversation_id (FK CASCADE), role, content, model, is_favorite, created_at | role ∈ {'user','assistant'} |
| `Tag` | id, user_id (FK CASCADE), name | unique per user |
| `message_tags` | message_id, tag_id | M2M association table |
| `UsageStat` | id, user_id (FK), period_start (first of month), tokens (BIGINT UNSIGNED) | UNIQUE(user_id, period_start) for upsert |
| `Prompt` | id, user_id, title, description, body, is_public, is_staff | Tagged via prompt_tags M2M |
| `PromptChain` | id, user_id, title | Ordered prompts via chain_prompts (with position column) |
| `Ticket` / `TicketMessage` | Support ticket subsystem | sender_type ∈ {'user','admin','ai'} |
| `Notification` / `NotificationRead` | Admin broadcast or targeted notifications; archived flag | |

Cascade deletes: `User → Conversation → Message` (all `ondelete="CASCADE"` at DB level + `passive_deletes=True` in SQLAlchemy).

All `created_at` columns use `datetime.now(tz=UTC)` callables (not `datetime.utcnow`) to ensure timezone-aware objects.

---

## 11. Key Conventions

**Naming**
- Blueprints named after domain (`chat`, `auth`, `billing`, `prompt`, `chain`).
- Route functions named `{resource}_{action}` (e.g., `edit_conversation_title`, `delete_conversation_route`).
- Services in `app/services/` wrap model-layer functions, adding business logic (sorting, title generation, pagination).

**File organization**
- Model definitions and CRUD helpers co-located in `app/models.py`.
- Service layer (`app/services/`) provides the interface routes call; routes do not call ORM directly except in simple cases.
- Providers are pure I/O adapters with no Flask context dependency.

**Error handling**
- Providers raise standard SDK exceptions (`APIConnectionError`, `APIStatusError`, `OpenAIError`, `GoogleAPICallError`) plus app-defined `ModelAccessError`.
- `AIStreamer.chat()` catches `ModelAccessError` and recurses with `fallback_model` (cycle-guarded via `_visited` set).
- HTTP error handlers registered in `create_app()` for 404 and 500; rate-limit 429 via blueprint error handler.
- All `logger.error/warning` calls include structured fields (`user=%s conv=%s model=%s`).

**Decorators on routes** (applied in order, outer→inner):
```python
@chat.route("/answer", methods=["GET","POST"])
@limiter.limit(plan_limits)
@login_required
@require_active_subscription
@enforce_token_quota
def answer(): ...
```

**No background workers / no asyncio**
The app is synchronous Flask with blocking Gunicorn gthread workers. There are no Celery tasks, no asyncio event loops, no WebSocket connections server-side. Streaming is synchronous generator-based, compatible with gthread.

**Testing**
- `conftest.py` provides `app` and `client` fixtures using `TestingConfig` (SQLite in-memory).
- Tests mock external calls (Mailgun, Stripe) via `unittest.mock.patch`.
- CI runs `docker compose run --rm test` which executes `pytest`.

---

## 12. AI/LLM Integration — Deep Dive

### Provider SDK clients

| Provider | SDK | Client construction |
|---|---|---|
| OpenAI | `openai==2.8.1` | `OpenAI()` — reads `OPENAI_API_KEY` from env |
| Anthropic | `anthropic==0.73.0` | `Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))` |
| Google Gemini | `google-genai==1.51.0` | `genai.Client()` — reads `GEMINI_API_KEY` / `GOOGLE_API_KEY` from env |

Clients are constructed once per provider instance (one per `ProviderRegistry` per `AIStreamer` per request). No connection pooling at the SDK level is configured — the underlying `httpx` client manages this transparently.

### Streaming implementation per provider

**Anthropic** (`app/providers/anthropic_provider.py`):
```python
with self.client.messages.stream(**stream_kwargs) as stream:
    for event in stream:
        text = _extract_text_from_event(event)  # isinstance check on ContentBlockDeltaEvent
        if text:
            yield text
```
Note: Anthropic disallows specifying both `temperature` and `top_p` simultaneously; the provider logs a warning and drops `top_p` if both are set.

**OpenAI** (`app/providers/openai_provider.py`):
The stream chunk format differs by model family. The provider handles three extraction paths:
1. `chunk.type == "response.output_text.delta"` — O3/Responses API events
2. `chunk.choices[0].delta.content` — standard Chat Completions
3. `chunk.candidates[0].delta.text` — O-model alternative structure

**Gemini** (`app/providers/gemini_provider.py`):
```python
stream = self.client.models.generate_content_stream(model=model, contents=contents, config=config)
for chunk in stream:
    text = getattr(chunk, "text", None)
    if text:
        yield text
```
Conversation history uses Gemini's role convention: `"user"` and `"model"` (not `"assistant"`). System prompt is passed via `GenerateContentConfig(system_instruction=...)`.

### Context assembly
Each provider calls `get_conversation_messages(conversation_id)` at stream time to build the full message list from the database. This means every chat turn incurs a DB read of all prior messages in the conversation — there is no in-memory conversation cache. The assembled list is appended with the current user message before sending to the LLM API.

### Prompt construction
System prompts come from (in priority order):
1. Per-request `system_prompt` argument (not currently used at the call site — always `None` from `chat.py:answer()`)
2. `MODEL_REGISTRY[model]["system_prompt"]` (only set for Gemini models)
3. Hardcoded fallback: `"You are an intelligent assistant."`

No dynamic prompt construction, RAG retrieval, tool/function calling, or structured output parsing is currently implemented.

### UI wiring
The chat interface is a single-page Jinja2 template (`app/templates/chat.html`) with inline JavaScript. It is a full-page reload app with progressive enhancement — the `/chat` route renders existing conversation messages server-side; subsequent messages are streamed and appended entirely client-side via `fetch` + `ReadableStream`. No React, Vue, or frontend build pipeline.

### Guardrails
- No AI output validation or structured output parsing.
- No content moderation layer (no OpenAI Moderation API call, no custom filter).
- Human-in-the-loop: none automated. The tagging system (`Tag`, `message_tags`) allows users to manually annotate messages.
- Token quotas act as an indirect guardrail against runaway usage.

### Response rendering
Accumulated tokens are parsed with `marked.parse(output)` on every chunk and injected as `innerHTML`. This means the DOM is updated on every chunk but the full string is re-parsed each time (not incremental). Code blocks and markdown are rendered in the browser.

### Prompt Builder / Chains
`PromptChain` + `Prompt` models allow users to save reusable prompt templates and multi-step chains. At chat time, `chat.py:chat_page()` concatenates chain prompt bodies (plus optional user context) into `prefilled_prompt`, which is inserted into the textarea. The chain content then becomes a single large user message — chains are not executed step-by-step against the LLM; they are string-concatenated and sent as one message.

---

## 13. AI Assistance — Portability to TOMIC

> TOMIC context: Dash-based Python options trading platform using `asyncio.new_event_loop()` daemon threads, a `STRATEGY_REGISTRY`/`RISK_CONFIG` central config pattern, tastytrade API, DXLink WebSocket streaming. Dash callbacks require all `State` IDs in the initial layout.

---

### 13.1 What maps cleanly

#### `MODEL_REGISTRY` pattern → TOMIC config extension
**Complexity: LOW**

`MODEL_REGISTRY` in `app/model_registry.py` is pure Python with no Flask dependency. It can be dropped directly into TOMIC as-is or merged into `RISK_CONFIG`/`STRATEGY_REGISTRY`. The three-layer merge in `build_generation_config()` is a clean pattern for letting TOMIC's strategy code select AI behavior profiles (e.g., `"coding"` for code generation tasks, `"summarize"` for position summaries).

What to lift: the dict structure, `build_generation_config()`, `PROFILE_OVERRIDES`, and `get_model_metadata()`. Rename to match TOMIC conventions if desired.

#### `AIProvider` ABC + all three provider implementations
**Complexity: LOW**

`app/providers/base_provider.py`, `anthropic_provider.py`, `openai_provider.py`, and `gemini_provider.py` have zero Flask imports. The only dependency is `app/services/conversation.py:get_conversation_messages()` — replace that call with TOMIC's own context-fetching logic (see §13.3).

What to lift: the full `providers/` directory. Swap `get_conversation_messages()` for a TOMIC-native context builder.

#### `ProviderRegistry` + `AIStreamer` (minus persistence)
**Complexity: LOW–MEDIUM**

`ProviderRegistry` maps provider keys to provider instances — this maps directly to TOMIC's `STRATEGY_REGISTRY` pattern. The core streaming loop in `AIStreamer.chat()` is also framework-agnostic; persistence and token-quota logic can be stripped or replaced.

What to lift: `ProviderRegistry`, the `chat()` generator loop and fallback recursion logic (`_visited` guard). Drop `MessagePersister` and `_inc_usage()` unless TOMIC needs token accounting.

#### `get_tokenizer()` in `app/tokenizer.py`
**Complexity: LOW**

Pure Python, no dependencies. The `lru_cache` wrapper on `tiktoken.get_encoding()` is directly reusable for token estimation before sending requests to the LLM.

#### `STRATEGY_REGISTRY` in `openai_provider.py`
**Complexity: LOW**

The `_EndpointStrategy` / `STRATEGY_REGISTRY` pattern for routing different OpenAI models to different API endpoints (`chat` vs `responses`) is already structurally identical to TOMIC's registry pattern. Lift verbatim.

---

### 13.2 What needs adaptation

#### Streaming to Dash UI
**Complexity: HIGH — biggest mismatch**

Syvrona's streaming relies on `flask.stream_with_context` returning a `text/plain` chunked HTTP response consumed by the browser's `ReadableStream` API. **Dash does not support this pattern.** Dash callbacks are synchronous request-response; a callback cannot return a streaming generator.

Options for TOMIC:
1. **Polling pattern**: Have a Dash callback trigger a background thread that writes streamed tokens into a shared queue/store (e.g., a `dcc.Store` updated via `dcc.Interval` polling). The interval callback reads from the store and updates the output div. Latency increases to poll interval (typically 500ms–1s).
2. **WebSocket via Flask-SocketIO or `dash-extensions`**: Run the streaming in a background thread on TOMIC's existing asyncio daemon, push tokens via WebSocket to the client. More complex but produces real token-by-token updates.
3. **Non-streaming (simplest)**: Collect the full LLM response before returning from the callback. Acceptable if TOMIC's AI features are advisory/analytical (e.g., position summaries, trade suggestions) rather than conversational.

For TOMIC's use case (trading assistant, not chat), option 3 is likely sufficient and avoids significant infrastructure complexity.

#### Context gathering
**Complexity: LOW–MEDIUM**

Syvrona builds context from `get_conversation_messages(conversation_id)` — a DB read of prior chat turns. TOMIC has richer structured context available:

| Syvrona source | TOMIC equivalent |
|---|---|
| Conversation history (Message rows) | Could be maintained in a `dcc.Store` or a lightweight in-memory list |
| Current model config | `MODEL_REGISTRY` (portable as-is) |
| System prompt | Could inject TOMIC market context: current positions, Greeks, P&L |
| (none) | `MarketDataService` cache — last quotes, IV, underlying prices |
| (none) | `PositionCache` — open positions, strikes, expirations |
| (none) | Screener data — filtered opportunity lists |

The prompt construction call in `AnthropicProvider.stream_response()` / `OpenAIProvider._build_context()` would need a TOMIC-specific context builder that serializes `PositionCache` and `MarketDataService` data into the system prompt or initial user turn. This is the highest-value adaptation — it's where Syvrona's generic "You are an intelligent assistant" becomes "You are a trading assistant with the following open positions: ...".

#### Dash layout constraint
**Complexity: MEDIUM**

Dash requires all `Output`/`State` component IDs to exist in the initial layout. An AI chat panel added to TOMIC must have its container `div` (and any `dcc.Store` for conversation state) present on initial render. This is an architectural constraint that must be respected at design time — the component IDs cannot be added dynamically.

Mitigation: design the AI panel as a collapsible sidebar with all IDs present at load but hidden by CSS until triggered.

#### Asyncio compatibility
**Complexity: MEDIUM**

Syvrona is synchronous. TOMIC's daemon threads run `asyncio.new_event_loop()`. If TOMIC calls a Syvrona provider's `stream_response()` generator from within an asyncio event loop, the synchronous SDK calls (`anthropic.messages.stream`, `openai.chat.completions.create`) will block the event loop thread. 

Mitigation options:
- Run LLM calls in a separate daemon thread (not on the asyncio loop) and queue results back.
- Use async SDK variants: `anthropic.AsyncAnthropic`, `openai.AsyncOpenAI`. These would require rewriting the provider `stream_response()` methods as `async def` generators.

---

### 13.3 Reuse vs. Rewrite Matrix

| Component | File(s) | Reuse | Notes |
|---|---|---|---|
| `AIProvider` ABC | `providers/base_provider.py` | **Direct lift** | Zero dependencies |
| `AnthropicProvider` | `providers/anthropic_provider.py` | **Direct lift** | Replace `get_conversation_messages()` call |
| `OpenAIProvider` + `_EndpointStrategy` | `providers/openai_provider.py` | **Direct lift** | Same substitution |
| `GeminiProvider` | `providers/gemini_provider.py` | **Direct lift** | Same substitution |
| `MODEL_REGISTRY` + `build_generation_config()` | `model_registry.py` | **Direct lift** | Pure Python |
| `get_tokenizer()` | `tokenizer.py` | **Direct lift** | Pure Python |
| `ProviderRegistry` | `services/ai_streamer.py` | **Direct lift** | |
| `AIStreamer.chat()` core loop | `services/ai_streamer.py` | **Adapt** | Strip Flask/DB persistence; adapt for asyncio if needed |
| Streaming HTTP response | `chat.py:answer()` | **Rewrite** | Dash has no equivalent; use polling or WebSocket |
| Client-side streaming JS | `templates/chat.html` | **N/A** | Dash uses Python callbacks, not custom JS fetch loops |
| CSRF rotation on stream | `chat.py:answer()` | **N/A** | Dash handles CSRF differently |
| Token quota enforcement | `limits.py`, `AIStreamer._inc_usage()` | **Adapt** | Replace MySQL upsert with whatever TOMIC uses for accounting |
| Markdown rendering | `marked.min.js` | **N/A** | Use `dcc.Markdown` in Dash |
| Conversation persistence | `models.py`, `services/conversation.py` | **Rewrite** | TOMIC has no message DB; use `dcc.Store` or add SQLite |

---

### 13.4 Recommended TOMIC Integration Sequence

1. **Copy `providers/` directory** and `model_registry.py`, `tokenizer.py` into TOMIC's source tree unchanged.
2. **Write a TOMIC context builder** function: takes `PositionCache`, `MarketDataService`, optional screener snapshot → returns a system prompt string. Inject as `system_prompt` argument to provider `stream_response()`.
3. **Choose streaming strategy** (polling vs. WebSocket vs. blocking): for a first pass, use the blocking/non-streaming approach — call `"".join(provider.stream_response(...))` in a background thread and return the result to a Dash callback via a `dcc.Store`.
4. **Add an AI panel to the Dash layout** at startup (all IDs present). Wire a text input + submit button to a callback that dispatches to `ProviderRegistry.get_provider()`.
5. **Resolve asyncio**: if the AI call runs on a daemon thread with its own event loop, synchronous SDK clients work fine. If TOMIC routes the call through an existing asyncio loop, switch to async SDK clients.

---

### 13.5 Effort Estimates

| Task | Effort |
|---|---|
| Copy providers + registry into TOMIC | 1–2 hours |
| TOMIC context builder (PositionCache → system prompt) | 2–4 hours |
| Non-streaming Dash callback (blocking) | 2–4 hours |
| Streaming via polling (`dcc.Interval` + `dcc.Store`) | 1–2 days |
| Streaming via WebSocket | 3–5 days |
| Async provider rewrite (AsyncAnthropic / AsyncOpenAI) | 1 day |
| Conversation history in `dcc.Store` | 2–4 hours |
| Model selector UI in Dash | 2–4 hours |

**Total for a non-streaming MVP AI panel in TOMIC: ~1–2 days of focused work.**  
The providers and registry are the hard part — they're already done and portable.
