# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Syvrona

Multi-provider AI chat SaaS (Flask, MySQL, Redis, Stripe; OpenAI, Anthropic and Gemini
behind one streaming endpoint), built by Termondt Tech in 2024 and 2025. **Retired: not
hosted, no customers. Public since 2026-11-06** (Apache-2.0 code, CC BY 4.0 docs) as the
"before" artifact for Argus. **Modernized 2026-11-06**: current dependencies, models and
defect fixes, still not hosted. Work here is hygiene, extraction of reusable parts, or the
public review sample, not product development, unless Rich says otherwise. Everything
pushed, issue and PR text included, is public; secret scanning and push protection are on.

| Read this | For |
|---|---|
| [`docs/syvrona-modernization-change-record-2026-11-06.md`](docs/syvrona-modernization-change-record-2026-11-06.md) | What the modernization changed: dependency and model tables, every defect fixed (D1 to D22) with its test, the verification evidence, what could not be verified, open actions. **Read before touching the chat path.** |
| [`docs/syvrona-modernization-and-value-assessment-2026-11-05.md`](docs/syvrona-modernization-and-value-assessment-2026-11-05.md) | Current state, the gap inventory, the defects found by reading (D1 to D12), the P0 to P3 action list, the open-source plan. **Read before any change.** |
| [`docs/architecture-reference-2026-06-30.md`](docs/architecture-reference-2026-06-30.md) | The long-form architecture reference (the former CLAUDE.md): data flow, schema, and §13 on porting the AI layer to TOMIC. Predates the 2026-11-06 chat-path rewrite; where they differ, this file and the change record win. |
| [`docs/git-history-secret-scan-2026-11-06.md`](docs/git-history-secret-scan-2026-11-06.md) | AI-3 result: no credential in any commit, ref, issue or PR; the one false positive; what a public flip would still expose (the personal commit email). |
| `README.md`, `NOTICE` | The public front page (retired status, local setup, licence) and the licence map: Apache-2.0 code, CC BY 4.0 docs (`LICENSE-docs`), MIT for the two bundled JS libraries (`THIRD_PARTY_LICENSES`). |
| `docs/deployment.md`, `docs/digital_ocean_install.md` | The droplet deploy and provisioning procedures. Historical: the site is down. |
| `docs/releases/`, `CHANGELOG.md` | One note per tag; new notes copy `docs/releases/release_template.md`. |
| `docs/roadmap.md` | The 2025 product roadmap. Historical, not a plan. |

## Current phase

**Modernized 2026-11-06** (AI-4, AI-5, AI-6, AI-7's lint and pins): Python 3.13, every
dependency current under a seven-day cooldown in hash-pinned locks, the registry on GPT-6,
Claude 5.5 and Gemini 3.5 to 4, defects D1 to D12 fixed plus ten more found on the way
(D13 was a security bug: `/answer` accepted another user's conversation id), 118 tests on
SQLite and MySQL 8.0. **Not verified: any live provider call**, because every key is
revoked. Published the same day (SC-2, SC-4, SC-5 done). Not started, each Rich's call:
security hardening and infrastructure (AI-9, AI-10) and the Rails-Review sample (AI-12).
→ the change record, §6 and §7.

## Build / test / lint

Docker-first, Python 3.13 everywhere: the image pins `python:3.13.17-slim-trixie`, CI lint
runs 3.13, the local `.venv` is 3.13. The Dockerfile has two stages: `test` (runtime plus
pytest; the compose `test` service and CI) and `runtime` (gunicorn; the default target).

```
cp .env.example .env                       # fill in values; never commit .env
docker compose up -d --build               # web on :5001 (container :5000), mysql :3306, redis
docker compose build test && docker compose run --rm test   # 118 tests on SQLite; what CI runs
docker exec -it syvrona-ai-web-1 flask db upgrade            # also builds an empty database
```

Outside Docker, `app/config.py` raises at **import** time without `DATABASE_URL` and
`SECRET_KEY`, so even the test suite needs them in the environment:

```
DATABASE_URL=sqlite:///:memory: SECRET_KEY=test python -m pytest -q
DATABASE_URL=sqlite:///:memory: SECRET_KEY=test python -m pytest tests/test_chat_answer.py -q
black --check app tests app.py conftest.py && flake8 app tests app.py conftest.py   # CI lint
docker run --rm -v "$PWD":/repo:ro ghcr.io/gitleaks/gitleaks:v8.28.0 git /repo --log-opts="--all -m" --redact --no-banner   # what Secret Scan CI runs
```

The same suite runs on MySQL when `TEST_DATABASE_URL` points at a disposable database
(`mysql+pymysql://...`); do that after touching models, the usage upsert or migrations,
and run `flask db check` against a freshly upgraded database to catch model drift.

`black` line length 88; `flake8` ignores E203 and W503; `migrations/` is excluded from
both. CI pins black 26.10.1 and flake8 7.5.0 (neither is in `.venv`; install those exact
versions). Black reads `requires-python` from `pyproject.toml`, so it formats for 3.13.
Lint explicit paths locally: `pyproject.toml` sets `exclude`, which turns off black's
default skipping of `.venv`, so `black .` would crawl it.

**Dependencies.** Direct dependencies live in `pyproject.toml`, with the four SDK majors
capped. `requirements.txt` (runtime) and `requirements-dev.txt` (plus pytest) are
hash-pinned locks, installed with `--require-hashes`. Regenerate both; never edit them by
hand. The lock takes nothing published in the last seven days:

```
docker run --rm -v "$PWD":/src -w /src python:3.13.17-slim-trixie sh -c 'pip install -q uv==0.13.6 && C="--universal --python-version 3.13 --generate-hashes --no-header --exclude-newer $(date -u -d "-7 days" +%Y-%m-%dT00:00:00Z)" && uv pip compile pyproject.toml $C -o requirements.txt && uv pip compile pyproject.toml --extra dev $C -o requirements-dev.txt'
```

Dev server: `python app.py` (host and port from `FLASK_RUN_HOST` / `FLASK_RUN_PORT`) or
`flask run` (the CLI reads `.env` through python-dotenv). Production:
`gunicorn -c app/gunicorn.conf.py "app:create_app()"`.

**Credentials load from `.env` only** (compose `env_file: .env`, `load_dotenv()` in
`app.py` before the app is imported, the `flask` CLI). The `.flaskenv*` files were deleted
on 2026-11-06; do not recreate them, since the `flask` CLI would read one silently.
`.env.example` lists every variable name with no values.

## Architecture at a glance

Application factory (`app/__init__.py::create_app`) registers twelve blueprints, one per
domain (`main`, `auth`, `admin`, `billing`, `health`, `chat`, `support`, `prompt`, `chain`,
`knowledge_base`, `tags`, `ratelimit_logging`). Models and their CRUD helpers live
together in `app/models.py`; `app/services/` wraps them with business logic; routes call
services, not the ORM, except in simple cases.

**The chat path, which is the only path that matters:**

```
POST /answer (chat.py::answer)     JSON {message, model?, conversation_id?}; POST only
  @limiter.limit(plan_limits)      Flask-Limiter (Redis; memory:// in tests), keyed user-id-or-IP
  @login_required
  @require_active_subscription     subscription_status in {active, trialing}; admins bypass
  @enforce_token_quota             this month's UsageStat vs TOKEN_QUOTAS[tier]; 402 if over
  refuse before streaming          400 bad input · 404 conversation not the caller's · 413 too long
  → AIStreamer(app.extensions["ai_providers"]).chat(...)   services/ai_streamer.py: THE boundary
      load history once; fit_history() trims oldest first to the model's input budget
      ProviderRegistry.get(provider)   built on first use, one per process
      provider.stream(ChatRequest)     pure adapter, yields text deltas
      ModelAccessError before any text → next fallback_model in the validated chain
      success → user + assistant Message + add_usage_tokens() in ONE commit
      failure → nothing saved; tokens already streamed are still charged
  → text/plain stream with X-Conversation-Id and a rotated X-CSRFToken
```

`app/providers/base_provider.py` is the contract: a frozen `ChatRequest` in (messages,
system prompt, `max_output_tokens`, `generation_config`, `options`), text deltas out,
`ModelAccessError` for HTTP 403, 404 or 429 ("try the fallback"), `ProviderError` for a
failure reported inside the stream. Adapters never touch the database or Flask. OpenAI
uses the Responses API with `store=False` (Chat Completions via `options.endpoint`);
Anthropic forwards only text deltas, skipping thinking deltas; Gemini maps `assistant` to
`model`. Keep every model call behind `AIStreamer.chat`; nothing else may call an SDK.

`app/model_registry.py` keys are the providers' API model IDs. Each entry has `provider`,
`display_name`, `context_window`, `max_output_tokens`, `generation_config`, `options`, and
optionally `system_prompt` and `fallback_model`. `validate_registry()` runs at import, so a
bad entry stops the app instead of failing one chat request.

Client side is one Jinja template with inline JavaScript (`app/templates/chat.html`):
`fetch` + `ReadableStream`, re-parsing the accumulated text with `marked` on every chunk,
applying the rotated CSRF token from the response header. No frontend build.

Persistence: `User → Conversation → Message` with DB-level `ON DELETE CASCADE` and
`passive_deletes=True`; messages are ordered by `(created_at, id)` because MySQL `DATETIME`
has one-second resolution. `Tag` is per user and M2M to messages, prompts and chains;
`Prompt` and `PromptChain` (ordered via `chain_prompts.position`) are the prompt library;
`UsageStat` has `UNIQUE(user_id, period_start)`, which backs both the quota lookup and the
portable upsert in `models.py::add_usage_tokens`. Datetimes are written as aware UTC into
naive columns, so stored values are UTC wall time.

## Landmines (verified 2026-11-06)

- **Current models refuse most sampling settings.** The Anthropic 2.x SDK has no
  `temperature`/`top_p`/`top_k` and Claude 5.5 answers 400 to them; Gemini 3.6+ and 4
  ignore them; GPT-5/6 accept `temperature`/`top_p` only with `reasoning_effort` `"none"`.
  The registry validation enforces this; do not route around it with `extra_body`.
- **`gemini-4-argon` on `generate_content_stream` is unverified.** Google's own examples
  for it use the newer Interactions API. A 404 there falls back to `gemini-3.8-flash`.
- **Token counts are estimates.** Every model is counted with `o200k_base`; Claude 5.5's
  tokenizer counts about 30% more. Context budgets keep 25% headroom; quotas are approximate.
- The migration chain's root is `baseline_2025_05`, added 2026-11-06 because the original
  first revision assumed a `user` table made by `db.create_all()`. Databases bootstrapped
  that way already sit above it.
- `google-genai` is held at 2.34 by the cooldown (3.0.0 shipped the day of the lock), and
  `redis` at 7.4 because `limits[redis]` caps it below 8. A major bump is a reviewed change.
- A first turn that fails leaves an empty conversation: it is created before streaming so
  the response header can carry its id.
- The Dockerfile does `COPY . .` in both stages; `.dockerignore` is all that keeps `.env*`,
  logs, `.venv/`, `.git/` and `docs/` out. `tests/` and `conftest.py` stay in the context
  for the `test` stage. Images built before 2026-11-06 carry the old keys, now revoked.
- The `knowledge_base` blueprint is four static help pages, not retrieval.

## Conventions

- Route functions are `{resource}_{action}` (`edit_conversation_title`,
  `delete_conversation_route`). Decorator order on protected routes is
  `@limiter.limit` → `@login_required` → `@require_active_subscription` →
  `@enforce_token_quota`, cheapest first. Look up rows with `db.session.get` or
  `db.get_or_404`, never the legacy `Model.query.get`.
- Ownership is checked on every route that takes an id, with
  `services/conversation.py::get_user_conversation` for conversations: not found and not
  yours are the same 404.
- Adding a model is a registry entry plus the provider's documented limits; the registry
  tests keep retired IDs out. Structured log fields everywhere: `user=%s conv=%s model=%s`.
- Every defect fix lands with a test that fails without it. `tests/fakes.py::FakeProvider`
  stands in for every SDK; a test that gets a streamed response must drain it.
- A release is a tag `vX.Y.Z`, a note at `docs/releases/X.Y.Z.md` from the template, and
  a line in `CHANGELOG.md`. Release Drafter and the autolabeler key on PR titles
  (`fix`, `feature`, `docs`, `architecture`).
- Assessments and design documents follow the Argus shape: `docs/<slug>-<YYYY-MM-DD>.md`,
  a `**Type:**` line saying what the document may and may not change, "Verified against
  source: <sha>", numbered sections, evidence by `module::name` anchor, `> **Unverified:**`
  inline, and a P0 to P3 action table.
- Vendoring third-party code into `app/static/` means a `NOTICE` entry (name, version,
  path, licence) and its upstream licence text in `THIRD_PARTY_LICENSES`. Pin new
  workflow actions by full commit SHA with the tag as a trailing comment.
- Secrets only from the environment. Never print a value from `.env*` or `.flaskenv*`
  into a document, a log or a commit; `.claude/settings.json` denies reading them.
- A gitleaks hit is a real key until reviewed. A reviewed false positive gets an inline
  `# gitleaks:allow` on the current line, or its fingerprint in `.gitleaksignore` if it lives
  only in history.
- Keep this file short. A resolved question gets one current-state sentence here and a
  pointer into `docs/`; relocate narrative, never delete it.

## File structure (condensed)

```
app.py                      WSGI entry; load_dotenv() before importing the app; create_app()
app/
  __init__.py config.py     factory + blueprints + lazy ProviderRegistry; Config reads env at import
  extensions.py limits.py   the Limiter; plan_limits(), enforce_token_quota
  decorators.py             admin_required, require_active_subscription
  model_registry.py         MODEL_REGISTRY, DEFAULT_MODEL_KEY, validate_registry() (runs at import)
  tokenizer.py              count_tokens(): o200k_base for every model, an estimate
  models.py                 all SQLAlchemy models + CRUD helpers + add_usage_tokens (portable upsert)
  services/                 ai_streamer.py (THE boundary), conversation.py, signup.py, tags.py
  providers/                base_provider.py (contract), openai_, anthropic_, gemini_provider.py
  chat.py                   /chat, /answer, /conversation/*, /messages/*/tags
  auth.py admin_routes.py billing.py support.py prompt.py chain.py tags.py knowledge_base.py routes.py health_routes.py
  templates/ static/        Jinja2 + inline JS; chat.html carries the streaming client
  gunicorn.conf.py          gthread, preload_app=False, max_requests=100 (low), /dev/shm heartbeat
migrations/                 Alembic, 15 revisions from baseline_2025_05, linear chain
tests/ conftest.py          118 tests; FakeProvider; SQLite StaticPool or TEST_DATABASE_URL; CSRF off
pyproject.toml              direct deps, pytest and black config; requirements*.txt are its locks
Dockerfile                  stages: base → test | runtime; tiktoken data baked in at build
docker-compose.yml          web (runtime), mysql:8.0, redis:8, test (test stage); override bind-mounts for dev only
.github/workflows/          test.yml, python-lint.yml, docker-build.yml, release-drafter.yml, secret-scan.yml;
                            every action pinned by commit SHA, every workflow has a `permissions` block
LICENSE NOTICE LICENSE-docs THIRD_PARTY_LICENSES   Apache-2.0 code, CC BY 4.0 docs, bundled MIT texts
docs/                       assessment, change record, scan record, architecture reference, deployment, releases/, roadmap
```
