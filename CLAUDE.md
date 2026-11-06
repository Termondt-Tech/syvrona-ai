# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Syvrona

Multi-provider AI chat SaaS (Flask, MySQL, Redis, Stripe; OpenAI, Anthropic and Gemini
behind one streaming endpoint), built by Termondt Tech in 2024 and 2025. **Retired: not
hosted, no customers, repository private.** Last code commit `a685431` (2025-12-19).
Work here is hygiene, modernization, extraction of reusable parts, or preparation for a
public export, not product development, unless Rich says otherwise.

| Read this | For |
|---|---|
| [`docs/syvrona-modernization-and-value-assessment-2026-11-05.md`](docs/syvrona-modernization-and-value-assessment-2026-11-05.md) | Current state, the gap inventory, the defects found by reading (D1 to D12), the P0 to P3 action list, the open-source plan. **Read before any change.** |
| [`docs/architecture-reference-2026-06-30.md`](docs/architecture-reference-2026-06-30.md) | The long-form architecture reference (the former CLAUDE.md): data flow, streaming, registries, schema, and §13 on porting the AI layer to TOMIC. |
| [`docs/git-history-secret-scan-2026-11-06.md`](docs/git-history-secret-scan-2026-11-06.md) | AI-3 result: no credential in any commit, ref, issue or PR; the one false positive; what a public flip would still expose (the personal commit email). |
| `README.md`, `NOTICE` | The public front page (retired status, local setup, licence) and the licence map: Apache-2.0 code, CC BY 4.0 docs (`LICENSE-docs`), MIT for the two bundled JS libraries (`THIRD_PARTY_LICENSES`). |
| `docs/deployment.md`, `docs/digital_ocean_install.md` | The droplet deploy and provisioning procedures. Historical: the site is down. |
| `docs/releases/`, `CHANGELOG.md` | One note per tag; new notes copy `docs/releases/release_template.md`. |
| `docs/roadmap.md` | The 2025 product roadmap. Historical, not a plan. |

## Current phase

**Assessment done 2026-11-05. T0 hygiene landed 2026-11-06**: `.dockerignore` rewritten
(AI-2) and the dead files removed (`run.back`, `test_config.py`, `tests/create_database.py`,
`instance/`, `node_modules/`, `db/`). **AI-1 done 2026-11-06**: Rich revoked every
provider key at its provider and deleted the three `.flaskenv*` files and `app.log`;
`.env` and `.env.prod` remain locally and hold only dead keys. The git-history scan (AI-3)
is done and clean, and the Secret Scan workflow (SC-3) re-runs it on every push. **SC-2
decided 2026-11-06**: keep the author email and publish by flipping this repository in
place, history included; the address is already public on four other repositories, so a
rewrite would hide nothing. Rich flips. **Repo-side publication prep done 2026-11-06**
(AI-11 in part, AI-7's pinning): Apache-2.0 licence, README reframed as a retired archive,
every workflow action pinned by SHA with an explicit `permissions` block. Left before the
flip: re-run both gitleaks scans on the final commit (SC-5); after it, secret scanning
and push protection (SC-4). The 48 open issues were closed as not planned with an archive
comment and the six merged branches deleted, both 2026-11-06; `master` is the only branch. → the assessment, §7 and §8, and the scan record, §6.

## Build / test / lint

Docker-first. Python 3.12 in the image (`python:3.12-slim`, unpinned patch); the local
`.venv` is Python 3.13, so prefer compose for anything that must match production.

```
cp .env.example .env                       # fill in values; never commit .env
docker compose up -d --build               # web on :5001 (container :5000), mysql :3306, redis
docker compose build test && docker compose run --rm test   # pytest on SQLite in-memory; what CI runs
docker exec -it syvrona-ai-web-1 flask db upgrade            # apply migrations (or: flask db migrate -m "...")
```

Outside Docker, `app/config.py` raises at **import** time without `DATABASE_URL` and
`SECRET_KEY`, so even the test suite needs them in the environment:

```
DATABASE_URL=sqlite:///:memory: SECRET_KEY=test python -m pytest -q
DATABASE_URL=sqlite:///:memory: SECRET_KEY=test python -m pytest tests/test_app.py::test_healthz -q
black --check app tests app.py conftest.py && flake8 app tests app.py conftest.py   # CI lint, green since 2026-11-06
docker run --rm -v "$PWD":/repo:ro ghcr.io/gitleaks/gitleaks:v8.28.0 git /repo --log-opts="--all -m" --redact --no-banner   # what Secret Scan CI runs
```

`black` line length 88; `flake8` ignores E203 and W503; `migrations/` is excluded from
both. CI pins black 26.10.1 and flake8 7.5.0 (neither is in `.venv`; install those exact
versions). Lint explicit paths locally: `pyproject.toml` sets `exclude`, which turns off
black's default skipping of `.venv`, so `black .` would crawl it.

Dev server: `python app.py` (host and port from `FLASK_RUN_HOST` / `FLASK_RUN_PORT`) or
`flask run` (the CLI reads `.env` through python-dotenv). Production:
`gunicorn -c app/gunicorn.conf.py "app:create_app()"`.

**Credentials load from `.env` only** (compose `env_file: .env`, `load_dotenv()` in
`app.py`, the `flask` CLI). The `.flaskenv*` files were deleted on 2026-11-06; do not
recreate them, since the `flask` CLI would read one silently. `.env.example` lists every
variable name with no values.

## Architecture at a glance

Application factory (`app/__init__.py::create_app`) registers twelve blueprints, one per
domain (`main`, `auth`, `admin`, `billing`, `health`, `chat`, `support`, `prompt`, `chain`,
`knowledge_base`, `tags`, `ratelimit_logging`). Models and their CRUD helpers live
together in `app/models.py`; `app/services/` wraps them with business logic; routes call
services, not the ORM, except in simple cases.

**The chat path, which is the only path that matters:**

```
POST /answer (chat.py::answer)
  @limiter.limit(plan_limits)      Flask-Limiter on Redis, keyed user-id-or-IP, tier from Stripe price id
  @login_required
  @require_active_subscription     User.subscription_status in {active, trialing}; admins bypass
  @enforce_token_quota             UsageStat for the month vs TOKEN_QUOTAS[tier]; 402 if over
  → AIStreamer().chat(...)         services/ai_streamer.py: THE single boundary every model call crosses
      get_model_metadata(model)    model_registry.py: provider key, display name, encoding, generation_config, fallback_model
      ProviderRegistry.get_provider(key)   openai | anthropic | gemini
      save user Message → stream provider tokens → save assistant Message (only on success)
      _inc_usage(prompt+completion tokens)  MySQL INSERT ... ON DUPLICATE KEY UPDATE, in `finally`
      on ModelAccessError → recurse with fallback_model (cycle-guarded by _visited)
  → Response(generate(), text/plain) with X-Conversation-Id and a rotated X-CSRFToken
```

Each provider (`app/providers/*_provider.py`) re-reads the full conversation from the
database at stream time and builds its own message list; there is no context cache and no
truncation. `OpenAIProvider` further routes by `openai_endpoint` (`chat` vs `responses`)
through `STRATEGY_REGISTRY`, built at import from `MODEL_REGISTRY`. Keep every model call
behind `AIStreamer.chat`; nothing else in the app may call a provider SDK.

Client side is one Jinja template with inline JavaScript (`app/templates/chat.html`):
`fetch` + `ReadableStream`, re-parsing the accumulated text with `marked` on every chunk,
applying the rotated CSRF token from the response header. No frontend build.

Persistence: `User → Conversation → Message` with DB-level `ON DELETE CASCADE` and
`passive_deletes=True`; `Tag` is per user and M2M to messages, prompts and chains;
`Prompt` and `PromptChain` (ordered via `chain_prompts.position`) are the prompt library;
`UsageStat` has `UNIQUE(user_id, period_start)` for the upsert. All `created_at` defaults
are `datetime.now(tz=UTC)`.

## Landmines (verified by reading, 2026-11-05)

- `AIStreamer._inc_usage` is **MySQL-only** (`sqlalchemy.dialects.mysql.insert`). The
  suite runs on SQLite, so `/answer` has no test and cannot have one until this is made
  portable (assessment D3).
- `chat.py::answer` defaults the model to `"gpt-3.5-turbo"`, which is not in the registry:
  a request without `model` is a 500. Use `DEFAULT_MODEL_KEY` (D7).
- `fallback_model` must be a registry entry. `gemini-2.5-flash` falls back to
  `gemini-2.0-flash`, which is not one, so that path ends in `ValueError`, not a retry (D6).
- `services/conversation.py::get_conversation` **raises `ValueError`** on a missing row;
  every caller in `chat.py` checks `is None`. Missing conversation = 500, not 404 (D1).
- `billing.py::create_checkout_session` calls `url_for("profile")`; the endpoint is
  `auth.profile` (D2).
- The Dockerfile does `COPY . .`; `.dockerignore` (rewritten 2026-11-06) is all that keeps
  `.env*`, `.flaskenv*`, logs, `.venv/`, `.git/` and `docs/` out of the image. **`tests/`
  and `conftest.py` must stay in the context**: the compose `test` service runs pytest
  inside the same image. Images built before 2026-11-06 carry the old keys, now revoked
  (AI-1).
- `requests` is imported by `app/utils.py` but not declared in `requirements.txt`.
- `encoding` is `cl100k_base` for every model; GPT-5.x use `o200k_base` and Claude and
  Gemini have no tiktoken encoding. Quota counts are approximate everywhere.
- 18 uses of the legacy `Model.query.get()` / `get_or_404()`; SQLAlchemy 2.1 compatibility
  with Flask-SQLAlchemy 3.1.1 is unverified.
- `extensions.py` defines `limiter` twice (the second wins; harmless).
- `billing.py` and `services/signup.py` write naive datetimes into tz-aware columns (D8).
- The `knowledge_base` blueprint is four static help pages, not retrieval. The README's
  "internal knowledge bases" wording overstates it.

## Conventions

- Route functions are `{resource}_{action}` (`edit_conversation_title`,
  `delete_conversation_route`). Decorator order on protected routes is
  `@limiter.limit` → `@login_required` → `@require_active_subscription` →
  `@enforce_token_quota`, cheapest first.
- Providers are pure I/O adapters: no Flask imports, SDK exceptions propagate, plus the
  app-defined `ModelAccessError` for "try the fallback". Structured log fields everywhere:
  `user=%s conv=%s model=%s`.
- Adding a model is a registry entry: `provider`, `display_name`, `encoding`,
  `generation_config`, optional `max_tokens`, `system_prompt`, `fallback_model`, and for
  OpenAI `openai_endpoint`. Anthropic rejects `temperature` and `top_p` together; the
  provider drops `top_p` and warns.
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
app.py                      WSGI entry; load_dotenv(); create_app()
app/
  __init__.py config.py     factory + blueprints; Config reads env, raises without DATABASE_URL/SECRET_KEY
  extensions.py limits.py   Redis + Limiter singletons; plan_limits(), enforce_token_quota
  decorators.py             admin_required, require_active_subscription
  model_registry.py         MODEL_REGISTRY, DEFAULT_MODEL_KEY, PROFILE_OVERRIDES, build_generation_config
  tokenizer.py model_limits.py  tiktoken by registry encoding; get_max_tokens
  models.py                 all SQLAlchemy models + CRUD helpers
  services/                 ai_streamer.py (THE boundary), conversation.py, signup.py, tags.py
  providers/                base_provider.py ABC; anthropic_, openai_ (+ _EndpointStrategy), gemini_provider.py
  chat.py                   /chat, /answer, /conversation/*, /messages/*/tags
  auth.py admin_routes.py billing.py support.py prompt.py chain.py tags.py knowledge_base.py routes.py health_routes.py
  templates/ static/        Jinja2 + inline JS; chat.html carries the streaming client
  gunicorn.conf.py          gthread, preload_app=False, max_requests=100 (low), /dev/shm heartbeat
migrations/                 Alembic, 14 revisions, linear chain
tests/test_app.py conftest.py   23 tests; SQLite StaticPool; CSRF off
docker-compose.yml          web, mysql:8.0, redis:8, test; docker-compose.override.yml bind-mounts for dev only
.github/workflows/          test.yml, python-lint.yml, docker-build.yml, release-drafter.yml, secret-scan.yml;
                            every action pinned by commit SHA, every workflow has a `permissions` block
LICENSE NOTICE LICENSE-docs THIRD_PARTY_LICENSES   Apache-2.0 code, CC BY 4.0 docs, bundled MIT texts
docs/                       assessment, architecture reference, deployment, releases/, roadmap (historical)
```
