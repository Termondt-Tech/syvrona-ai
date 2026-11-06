# Syvrona: what bringing it up to date costs, and what it is worth to Termondt Tech — assessment and action list (2026-11-05)

**Type: assessment. Not normative.** Nothing in the application code was changed, and
nothing was run. This is analysis plus a prioritized action list for Rich. The only
files written alongside it are documentation and tooling: `CLAUDE.md` (rewritten; the
2026-06-30 architecture reference it replaced is relocated unchanged to
[`docs/architecture-reference-2026-06-30.md`](architecture-reference-2026-06-30.md)),
`.env.example`, `.claude/settings.json`, two lines in `.gitignore`, and three links in
`README.md`.

Verified against source: `syvrona-ai` `master` @ `a685431` (committed 2025-12-19;
working tree read 2026-11-05). Termondt Tech's offering read from
`termondttech/drafts/site/offer-pages-notes.md` (2026-10-23), `drafts/site/syvrona-page.html`,
`drafts/resume/summary-and-termondt-tech.md` (2026-10-27) and
`reports/Reaching buyers for Termondt Tech services.md` (2026-10-23). Argus conventions
from `argus/CLAUDE.md`, `argus/PUBLIC.md` and
`argus/docs/designs/2026-10-21-public-extraction.md`. Dependency versions from PyPI on
2026-11-05. Repository metadata from `gh` on 2026-11-05.

---

## 0. The answer

- **Do not bring Syvrona fully up to date as a product.** The market answered in 2025
  (a week's free trial, a handful of users, nobody paid; `drafts/site/syvrona-page.html`),
  the category is the model makers' own apps, and the AI layer that was its reason to
  exist is now commodity. A full modernization is 5.5 to 8 working days (§3.9) before a
  single new feature, and a competitive feature set (tools, files, agents) is weeks more.
- **Do a bounded, archive-grade pass and open-source it.** Two and a half to four days
  (§3.9, Option B) puts the dependencies current, the model list current, the secrets out
  of the tree and the image, the CI green and the documents truthful. That is the state a
  public repository needs and the state the resume already implies.
- **Its value to Termondt Tech is as evidence, not as software.** The site already
  positions Syvrona as the "before" picture of the method behind Argus. A public
  repository with a Rails-Review-style pass applied to it (§4.2) is a worked sample of
  the $15,000 deliverable with no client confidentiality in the way, and it feeds the
  content cadence the go-to-market plan already commits to.
- **Reuse the shape, not much of the code.** About 600 lines (providers, registry,
  streamer facade, limits) are framework-free and portable (§5), but they predate tool
  use, structured output and async. For an agentic tool or a TOMIC panel, start from the
  current Anthropic SDK or Claude Agent SDK and carry over Syvrona's one good idea: every
  model call crosses one metered, logged, persisted boundary.
- **Three things are not optional, whatever else is decided (§8, AI-1 to AI-3):** rotate
  the keys sitting in plaintext in `.flaskenv`, `.flaskenv.prod` and `app/.flaskenv.dev`;
  fix `.dockerignore` so the production image stops carrying them; scan the git history
  for credentials before any flip to public.

## 1. Scope and what was read

Every Python module under `app/` (36 files, 5,040 lines), `conftest.py` and
`tests/test_app.py` (23 tests, 389 lines), all 14 Alembic migrations, the Docker and
compose files, the four GitHub Actions workflows, `requirements.txt`, the docs tree
(roadmap, deployment, install guide, 19 release notes), the chat template's inline
JavaScript, and the GitHub repository state (`gh repo view`, `gh issue list`,
`gh run list`). Env files were read for variable NAMES only; their values are not
reproduced anywhere in this document.

Not done, by instruction: the application was not started, the test suite was not run,
no dependency was installed. Every "would fail" claim below is from reading the code and
is labelled as such where it is an inference rather than a direct observation.

## 2. Where Syvrona stands

| Fact | Value | Source |
|---|---|---|
| Hosting | **Not hosted.** "Syvrona is no longer hosted." | `termondttech/drafts/site/syvrona-page.html` |
| Last code commit | `a685431`, 2025-12-19, "added models, removed older models, added config options" | `git log` |
| Last tagged release | `v1.4.8`, 2025-08-08 (19 release notes, `v1.0.0` to `v1.4.8`) | `git tag`, `CHANGELOG.md` |
| Repository | `Termondt-Tech/syvrona-ai`, **private**, proprietary `LICENSE`, 1 star | `gh repo view` |
| Open issues / PRs | 48 open issues (oldest 2025-05-21), 0 open PRs, 6 stale remote branches | `gh issue list`, `git branch -a` |
| CI on `master` | Pytest and Docker Build green; **Python Lint red** on the last two pushes (2025-11-20, 2025-12-19) | `gh run list` |
| Size | 5,040 lines of Python in `app/`; about 5,800 lines of templates and JS (excluding `marked.min.js`); 14 migrations in a linear chain | `wc -l`, `migrations/versions/` |
| Tests | 23, all in `tests/test_app.py`: health, signup, login, subscription gating, prompt CRUD. **None touch `/answer`, the providers, the Stripe webhook, the limiter or the quota.** | `tests/test_app.py` |
| Stack | Python 3.12 image, Flask 3.1, SQLAlchemy 2.0, MySQL 8.0, Redis 8, Gunicorn gthread, Stripe, Mailgun, hCaptcha; OpenAI, Anthropic and Gemini SDKs | `requirements.txt`, `docker-compose.yml` |
| Working tree residue | `app.log` (24 MB, gitignored, contains the DB password from pre-masking log lines), `instance/db.sqlite` (40 KB, 2024), `.venv` (Python **3.13**, not the image's 3.12), `node_modules/tailwindcss` with no `package.json` and no Tailwind reference in `base.html`, `run.back`, `test_config.py`, `tests/create_database.py`, empty `db/` | `ls`, `tail app.log` |

What it does, in one paragraph: a user signs up (email confirmation, honeypot, optional
hCaptcha), picks free or a Stripe plan (trial behind a feature flag), and chats with one
of nine models through a single streaming endpoint. Conversations, messages, tags,
prompts and prompt chains persist in MySQL. Two limiters stack on the chat endpoint:
per-plan request rate (Flask-Limiter on Redis) and a monthly token quota (a MySQL upsert).
There is an admin area (users, tickets, broadcast notifications), a support-ticket
subsystem with Mailgun alerts, and a four-page static "knowledge base". The full
architecture is in the relocated reference; the compact map is in `CLAUDE.md`.

## 3. What "fully up to date" means: the gap inventory

### 3.1 Dependencies (pinned → current on PyPI, 2026-11-05)

| Package | Pinned | Current | Distance | Note |
|---|---|---|---|---|
| `openai` | 2.8.1 | 3.46.0 | **major** | Streaming event shapes are exactly what `openai_provider.py` pattern-matches on (three heuristic paths). Read the 3.x migration guide before bumping. |
| `anthropic` | 0.73.0 | 2.6.0 | **two majors** | `anthropic_provider.py` imports `anthropic.types.ContentBlockDeltaEvent` and uses `client.messages.stream`. Both must be re-verified against 2.x. |
| `google-genai` | 1.51.0 | 3.0.0 | **two majors** | `GenerateContentConfig(**kwargs)` and `Part(text=...)` in `gemini_provider.py`. |
| `stripe` | 13.2.0 | 16.1.0 | **three majors** | `billing.py` still uses `stripe.error.SignatureVerificationError`, the pre-v8 module path. > **Unverified:** whether 16.x still exposes `stripe.error`; the current name is `stripe.SignatureVerificationError`. |
| `gunicorn` | 23.0.0 | 26.2.0 | three majors | Config file is small; low risk. |
| `cryptography` | 44.0.3 | 50.0.2 | six majors | Security-relevant; transitive for PyMySQL auth. |
| `redis` | 7.0.1 | 8.1.0 | major | Used only as the limiter store and an unused `redis_client`. |
| `SQLAlchemy` | 2.0.44 | 2.1.8 | minor line | 18 uses of the legacy `Model.query.get()` / `get_or_404()`. > **Unverified:** Flask-SQLAlchemy 3.1.1 (2023) against SQLAlchemy 2.1. |
| `certifi` | 2025.4.26 | 2026.10.23 | 18 months of CA bundle | |
| `Flask` / `Werkzeug` / `Flask-WTF` / `Flask-Limiter` | 3.1.2 / 3.1.3 / 1.2.2 / 4.0.0 | 3.1.3 / 3.1.9 / 1.3.0 / 4.1.1 | patch or minor | |
| `pydantic`, `tiktoken`, `pymysql`, `pytest`, `python-dotenv`, `google-api-core` | 2.12.4, 0.12.0, 1.1.2, 9.0.1, 1.1.0, 2.28.1 | 2.14.3, 0.14.0, 1.2.3, 9.2.0, 1.2.4, 2.44.0 | minor | |
| `Flask-Login`, `Flask-SQLAlchemy`, `Flask-Migrate`, `flask-hcaptcha`, `httpx`, `Jinja2`, `pytest-flask` | | unchanged | current | |
| **`requests`** | **not declared** | | | `app/utils.py` imports it directly; it arrives only transitively (via `stripe`, `google-api-core`). An undeclared direct dependency. |

The file is a `pip freeze` snapshot (transitive pins such as `annotated-types`, `anyio`,
`sniffio` listed beside direct ones) without hashes. Argus's pattern, direct dependencies
in `pyproject.toml` and a hash-pinned `requirements.txt` generated by pip-tools, is the
right end-state and costs an hour.

### 3.2 Runtime and infrastructure

- **`python:3.12-slim`** is unpinned at the patch level; Argus pins `python:3.12.13-slim-bookworm`
  and runs CI on the same interpreter. The local `.venv` is Python 3.13, so dev and prod
  interpreters already differ.
- **`mysql:8.0`.** MySQL 8.0 left Oracle's premier support in April 2026; the LTS line is
  8.4. > **Unverified:** the Docker Official Image's own deprecation schedule for the
  `8.0` tag. Upgrading is an in-place `mysql_upgrade`-free step for 8.0 → 8.4, but it needs
  a backup first (`docs/deployment.md` has the procedure; issue #109 "Backup mysql
  database" is still open).
- **GitHub Actions** pinned by mutable tag (`actions/checkout@v4`, `actions/setup-python@v5`,
  `release-drafter@v6`, `docker/setup-buildx-action@v3`). Argus pins by full commit SHA and
  is on `checkout` v7.0.1 / `setup-python` v7.0.0. Two workflows (`test.yml`, `docker-build.yml`)
  have no `permissions:` block, so they run with the repository default.
- **Python Lint is red on `master`** and has been since 2025-11-20. The two model-registry
  commits were pushed without running `black`.
- **Gunicorn** `max_requests = 100` with `preload_app = False` recycles every worker every
  100 requests, and each recycle re-runs `create_app()` and rebuilds the SQLAlchemy pool
  (`gunicorn.conf.py`). Fine as a leak guard on a tiny site; wrong as a default.
- **Sizing documents disagree.** `docs/digital_ocean_install.md` provisions a 1 GB droplet
  with a 1 GB swapfile; `mysql-conf/syvrona.cnf` sets `innodb_buffer_pool_size = 1G`
  "safe for 4GB host". On the documented droplet that configuration would starve the
  application.

### 3.3 The model registry is a year old

`app/model_registry.py` carries nine models (3 OpenAI, 3 Anthropic, 3 Gemini) pinned in
November and December 2025.

| Entry | Status on 2026-11-05 |
|---|---|
| `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101`, `claude-haiku-4-5-20251001` | Superseded. The current family is Claude 5.5: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. `max_tokens: 64000` should be re-checked against each model's output limit. |
| `gpt-5.2-chat-latest` (the default), `gpt-5.1-2025-11-13`, `gpt-5.1-codex` | Late-2025 IDs. > **Unverified:** which are still served; check OpenAI's model list before shipping. |
| `gemini-3-pro-preview`, `gemini-2.5-pro`, `gemini-2.5-flash` | `gemini-3-pro-preview` is a preview ID; > **Unverified:** current GA names. |
| `fallback_model: "gemini-2.0-flash"` on `gemini-2.5-flash` | **Broken by construction.** `gemini-2.0-flash` is not in the registry, so `AIStreamer.chat` resolves `provider = ""` and `ProviderRegistry.get_provider("")` raises `ValueError`, which is not `ModelAccessError` and so is not caught: the fallback path ends in a 500. A fallback target must itself be a registry entry. |
| `encoding: "cl100k_base"` on every model | GPT-5.x tokenizes with `o200k_base`; Claude and Gemini have no tiktoken encoding at all. Quota counts are therefore approximate for every model and systematically wrong for OpenAI. Anthropic exposes a token-count endpoint; the honest fix is a per-provider counter behind the same interface. |
| `chat.py::answer` default `model = data.get("model", "gpt-3.5-turbo")` | Not in the registry; a request without a model field yields a 500. Should be `DEFAULT_MODEL_KEY`. |

### 3.4 Defects found by reading

Classified the way Argus investigations classify (defect = the code does something other
than its own documentation says; design gap = the code does what was intended and the
intent did not cover this). None was executed; each is an inference from the source,
with the anchor.

| # | Anchor | What | Class |
|---|---|---|---|
| D1 | `services/conversation.py::get_conversation` raises `ValueError` when the row is missing; every caller in `chat.py` tests `if convo is None` | A request for a non-existent conversation id is a 500, not the intended 404. The `None` branch is dead code. | defect |
| D2 | `billing.py::create_checkout_session` builds `url_for("profile")` | No endpoint is named `profile` (it is `auth.profile`); Flask raises `BuildError`, swallowed by the bare `except` into a 500 JSON. > **Unverified:** whether any template still posts to this route; `subscribe()` is the path the UI uses. | defect |
| D3 | `services/ai_streamer.py::AIStreamer._inc_usage` uses `sqlalchemy.dialects.mysql.insert(...).on_duplicate_key_update` | MySQL-only. The test suite runs on SQLite, so `/answer` cannot be exercised in tests at all. This is why the chat path has zero coverage. | design gap |
| D4 | `AIStreamer.chat` saves the user message before the provider call and the assistant message only on success | A provider failure leaves an unanswered user turn in history; the user's natural retry sends it twice. | design gap |
| D5 | all three providers call `get_conversation_messages(conversation_id)` and send every row | No context-window management. A long conversation eventually exceeds the model's limit and every turn fails from then on. | design gap |
| D6 | `ai_streamer.py` fallback chain, `model_registry.py` | Terminal fallback not in registry (§3.3). | defect |
| D7 | `chat.py::answer` | Default model string not in registry (§3.3). | defect |
| D8 | `billing.py` `datetime.fromtimestamp(...)`; `services/signup.py` `datetime.now()` | Naive datetimes written into columns whose defaults are tz-aware (`datetime.now(tz=UTC)` in `models.py`). Mixed semantics in the same table. | defect |
| D9 | `extensions.py` | `limiter = Limiter(...)` is defined twice; the second wins. Harmless, confusing. | hygiene |
| D10 | `openai_provider.py::OpenAIProvider.stream_response` | Three heuristic chunk-extraction paths; `ModelAccessError` raised only on `code == "model_not_found"`. A deprecated model that returns a different error code bypasses the fallback. | design gap |
| D11 | `utils.py::send_mailgun_message` | `requests.post` without a timeout; a Mailgun stall holds a Gunicorn thread indefinitely. | defect |
| D12 | `limits.py::enforce_token_quota` reads `UsageStat` per request; issue #124 "Add index to usage stats table" is open | The `UNIQUE(user_id, period_start)` constraint already gives MySQL an index for this lookup; the issue is probably moot. Verify with `EXPLAIN` before closing. | hygiene |

### 3.5 Security and secrets hygiene

- **The production image carries live credentials.** `.dockerignore` excludes `.env` and
  `*.log` but not `.flaskenv`, `.flaskenv.prod`, `app/.flaskenv.dev`, `.env.prod`, `.venv/`
  (it lists `venv/` and `.env/`, neither of which exists), `node_modules/`, `instance/` or
  `.git/`. `Dockerfile` does `COPY . .`. Every image built from this tree therefore
  contains a live Stripe secret key, OpenAI and Anthropic keys, the Flask `SECRET_KEY`, a
  SQLite file, a Python 3.13 virtualenv and the full git history. **No image built from
  the current tree should be pushed anywhere.**
- **Keys in plaintext on disk.** `.flaskenv` (dev) and `.flaskenv.prod` carry what look
  like live OpenAI, Anthropic and Stripe credentials; `.env` and `.env.prod` carry the
  full set including Mailgun and hCaptcha. All are gitignored and `git log --all` shows
  none was ever committed. They still have to be rotated: they have sat in a working tree,
  a log file and (per the previous bullet) every image ever built. `app.log` logs the
  database URL with its password unmasked (the `_mask_url` helper in `app/__init__.py`
  post-dates those lines).
- **Session cookies** carry no `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY` or
  `SESSION_COOKIE_SAMESITE` setting; no CSP or security headers (`docs/best_practices.md`
  recommends Flask-Talisman and the app does not use it).
- **Markdown rendering** sets `innerHTML = marked.parse(...)` in `chat.html` and
  `conversation_view.html` without a sanitizer. `marked` passes raw HTML through, so an
  assistant reply containing a `<script>` or `<img onerror>` executes in the user's own
  session. Same-user scope, so low impact, but it is the textbook fix (DOMPurify) and a
  reviewer will name it first.
- **Credential loading is in three places**: compose `env_file: .env`, `app.py`'s
  `load_dotenv()`, and the `flask` CLI's `.flaskenv`. That is how a dev file and a prod
  file came to hold the same OpenAI key.
- What is right: password hashing (Werkzeug PBKDF2), CSRF on forms with per-stream token
  rotation, Stripe webhook signature verification, parameterized SQL throughout (no
  `text()` with interpolation anywhere; the only `text("SELECT 1")` is the readiness
  check), ownership checks on every conversation, message and tag route, a non-root
  container user, hCaptcha and honeypots on signup and login, and an idempotent limiter
  init.

### 3.6 Tests and portability

- 23 tests, none on the chat path (D3 explains why). No test for the Stripe webhook, the
  limiter tiers, the quota decorator, the admin routes, the ticket flow or any provider.
- No fakes exist for the three providers; `ProviderRegistry` and `AIStreamer` accept
  injected providers, so adding a `FakeProvider` that yields a fixed token sequence is a
  small change and unlocks the whole path once D3 is fixed.
- `Config` validates `DATABASE_URL` and `SECRET_KEY` **at import time**, so `pytest` with
  a bare environment fails before `conftest.py` can inject test config. The compose `test`
  service sets both; a local run must export them. `CLAUDE.md` now says so.

### 3.7 Documentation truth

- `README.md` opens "AI-powered technician assistant platform ... designed to connect with
  OpenAI, internal knowledge bases, and third-party systems." The knowledge base is four
  static help pages (`knowledge_base.py`), there is no retrieval, and "technician" is a
  framing the product never had. The README also lists only OpenAI and Anthropic; Gemini
  shipped in 2025-11.
- `LICENSE` spells the product "Syvnora" twice.
- `CHANGELOG.md`: `1.0.0` is dated `2925-05015`; `1.4.3`, `1.4.2`, `1.4.1`, `1.2.1` and
  `1.2.0` carry 2024 dates for 2025 releases (their release notes and the git tags say 2025).
- `docs/roadmap.md` still lists "Google Ads campaigns (use $1000 credit by Aug 12, 2025)"
  as upcoming and a Track 1 that will never be built. It should be marked historical.
- `docs/best_practices.md` is a 200-line generic architecture primer with no Syvrona
  content; keep or drop, but do not let a reader mistake it for the project's own rules.
- The former `CLAUDE.md` (now `docs/architecture-reference-2026-06-30.md`) is accurate
  on the architecture and useful; its §13 TOMIC portability section is partly superseded
  by §5 below.

### 3.8 Product gaps if it were to compete again (not recommended)

For completeness: no tool or function calling, no file or image input, no web retrieval,
no image generation, no agent loop, no structured output, no async, no per-user model
tuning (issue #127), no usage dashboard, no export, no conversation search beyond
`ILIKE`. Prompt chains are string-concatenated into one user turn, not executed
step-by-step. Each of these is a feature the model makers' free tiers ship today.
Closing that gap is three to six weeks of work with no buyer identified.

### 3.9 Effort

Estimates assume the Argus way of working (an agent builds, Rich reviews) and no
production cutover.

| Tier | Work | Days |
|---|---|---|
| T0 Hygiene | Rotate every key; delete `.flaskenv*`, `app.log`, `instance/db.sqlite`, `node_modules/`, `run.back`, `test_config.py`, `tests/create_database.py`, `db/`; fix `.dockerignore`; verify with a build and `docker run --rm <img> ls -la /app` | 0.5 |
| T1 Dependency currency | Direct deps to `pyproject.toml`, hash-pinned lock; bump everything in §3.1 including the four SDK majors; re-verify each provider's streaming path; declare `requests`; suite green in compose | 1 to 2 |
| T2 Model registry | Claude 5.5 IDs, verified OpenAI and Gemini IDs, every fallback target present, `DEFAULT_MODEL_KEY` as the `/answer` default, per-provider token counting or an honest `o200k_base`/approximation note | 0.5 |
| T3 Security hardening | Cookie flags, Talisman/CSP, DOMPurify, Mailgun timeout, tz-aware datetimes (D8), D1/D2 fixes | 1 |
| T4 Tests | Portable upsert (D3), `FakeProvider`, tests for `/answer`, quota 402, limiter 429, webhook, fallback chain | 1 to 2 |
| T5 CI | SHA-pinned actions, `permissions: contents: read`, lint green, Python version pinned to the image's | 0.5 |
| T6 Infrastructure | Pin the base image, MySQL 8.4, gunicorn `max_requests`, reconcile `mysql-conf` with the droplet size, close #109 with a scripted backup | 0.5 to 1 |
| T7 Product gaps (§3.8) | Not recommended | 15 to 30 |

- **Fully up to date and re-hostable (T0 to T6): 5.5 to 8 days.**
- **Archive-grade and publishable (T0, T1, T2, T5, and §3.7 docs truth): 2.5 to 4 days.**
- **The minimum regardless of any decision (T0): half a day.**

## 4. Value to Termondt Tech's current offering

The offering, as published or drafted on 2026-10-23 (`offer-pages-notes.md`): the
**Rails Review** ($15,000, two weeks, for teams putting AI-written code into production;
deliverables are a written constitution and pinned invariants), **trading
infrastructure built and operated** (fixed scope, fixed fee, with an operate retainer),
and **fractional engineering leadership** ($6,000 or $12,000 a month; tabled as a
channel on 2026-10-26). The go-to-market plan (`Reaching buyers…`, 2026-10-23) commits
to a LinkedIn newsletter with two or three posts a week from 2026-11-09, two Hacker News
submissions, and local talks, and it says content's job is "the thing a buyer reads
before the call."

### 4.1 Where Syvrona already does work

- **It is the "before" in the story the site tells.** `drafts/site/syvrona-page.html`:
  built "with ChatGPT as a coding assistant... no rules file, no sign-off, no tests
  pinning what must never happen," and the lessons ("the prompt is the artifact worth
  reviewing, context has to be written down or it is gone, a model's output needs a person
  between it and anything that matters") became the Argus method. The resume names it.
  Today a buyer can read that claim but cannot check it.
- **It is evidence of range.** Argus proves rails, audit and execution. Syvrona proves a
  shipped, billed, multi-tenant web product: auth, email, Stripe subscriptions and
  webhooks, trials, tickets, admin, rate and quota tiers, streaming. For the fractional
  and trading-infrastructure buyers that is the "can this person ship a whole system"
  question answered a second way.

### 4.2 The highest-leverage use: a Rails Review applied to it, in public

The Rails Review's hardest sales problem, per the buyer research, is that "nobody searches
for it" and the buyer wants to see the deliverable before paying for one. Client work
cannot be shown. Syvrona can.

A public pass over Syvrona in the Rails Review's own shape would produce, with no NDA in
the way: the findings table (§3.4 and §3.5 are its first page), a short constitution for
the repository (the rules an agent must obey when touching billing, quotas, the model
boundary and secrets), and three or four pinned invariants as tests (every model call
crosses `AIStreamer.chat`; no credential file reaches the image; a fallback target is
always a registry entry; the quota is charged exactly once per call). That is a sample
report, a sample constitution and a sample invariant suite, published alongside the code
they describe, and it is one or two LinkedIn editions and a Hacker News comment in the
cadence the plan already budgets.

The reputational risk is the obvious one: the code is unguided-AI-assisted and reads like
it. The framing converts the risk: the whole point of the sample is that this is what
ordinary AI assistance produces and this is what a review finds. Publishing it unframed,
as "a product we built", would do the opposite. The README's first paragraph has to carry
the frame, as the Argus public README does ("a reference implementation... that ships
with a strategy proven to lose").

### 4.3 What it does not do

It does not sell the product. It does not support the trading-infrastructure offer
except as general evidence of delivery. It should not be re-hosted as a demo: a live
site needs keys, billing, moderation and uptime, and a dead site with a current
repository is a better story than a half-alive one.

## 5. Value for future tools, other contexts and agentic workflows

### 5.1 Component matrix

| Component | Lines | Framework-free | 2026 verdict |
|---|---|---|---|
| `providers/` (`AIProvider` ABC, three implementations) | about 550 | yes, except the import of `get_conversation_messages` | **A 2024-shaped abstraction.** Synchronous, text-only, no tool calling, no structured output, no MCP, no async, no images, no streaming of anything but text deltas. Each provider owns its own context assembly. The current Anthropic SDK and the Claude Agent SDK, the OpenAI Agents SDK, and routers such as LiteLLM or OpenRouter cover this surface with tool use included. Portable, but not worth porting; worth reading as a pattern. |
| `model_registry.py` (registry, `PROFILE_OVERRIDES`, three-layer `build_generation_config`) | 265 | yes | **The idea is good and matches how Argus treats config**: model identity, provider routing and sampling defaults as one declarative table with profiles layered on top. The table itself is stale (§3.3). Lift the shape into any new tool. |
| `services/ai_streamer.py` (`AIStreamer`, `ProviderRegistry`, `MessagePersister`) | 197 | needs the ORM for persistence and the upsert | **The one design worth carrying.** Every model call crosses one boundary that persists the turn, counts tokens, streams, persists the reply only on success, charges usage atomically, and recurses on a fallback with a cycle guard. That is the "single submission boundary" idea from Argus applied to LLM calls, and it is exactly what an agentic system needs for cost control and audit. Carry the design; rewrite the code async. |
| `limits.py` + Flask-Limiter + `UsageStat` | about 150 | Flask-bound | Per-tenant request rate and monthly token quota keyed on plan. Any paid AI tool, or any internal agent gateway with a budget, needs this. Reusable as-is inside Flask; trivial to re-express elsewhere. |
| `tokenizer.py` | 9 | yes | Wrong encoding for everything but legacy OpenAI (§3.3). Replace with per-provider counting. |
| `Prompt`, `PromptChain`, tags, public/staff/approved flags | about 500 incl. routes | Flask-bound | A **prompt registry with ownership, sharing and approval**: the data model generalizes to a library of rules files, review templates or constitutions. Chains are concatenated, not executed, so "agentic chains" is a rewrite, not an extension. |
| Auth, email confirm, reset, Stripe checkout + webhook + portal, trial flag, tickets, notifications, admin | about 2,000 incl. templates | Flask-bound | A **working small-SaaS shell** with no frontend build. If Termondt Tech ever needs a hosted client-facing tool (a client portal for review deliverables, a hosted dashboard), this saves one to two weeks over starting from zero. Stripe-python and the model list are the parts that have moved. |
| `chat.html` streaming client | 332 | n/a | `fetch` + `ReadableStream` + CSRF rotation. Correct and simple; of no use outside a Flask + Jinja app. |

### 5.2 Adapting it to agentic workflows

What an agentic use (a tool that plans, calls tools, reads files, iterates) needs that
Syvrona lacks: tool and function calling with a dispatch loop, structured outputs, async
I/O (Syvrona is sync Gunicorn threads by design; `docs/architecture-reference-2026-06-30.md`
§13 covers the asyncio mismatch), MCP or an equivalent tool protocol, file and image input,
an evaluation harness, traces, and guardrails on tool side effects. None of that is in
the repository, and the provider layer would be rewritten rather than extended to add it.

The recommendation is therefore: **start an agentic tool from the current Anthropic SDK
or the Claude Agent SDK, and carry over three Syvrona ideas** as design, not code: the
metered single boundary (`AIStreamer`), the declarative registry with profiles
(`model_registry.py`), and plan-keyed rate and token budgets (`limits.py`). Argus's own
rails (a kill switch, an audit chain, fail-closed staleness) are the other half of what
such a tool needs, and they are already written in the other repository.

### 5.3 TOMIC

The relocated reference's §13 stands as the plan if an AI panel in TOMIC is ever wanted:
copy `providers/`, `model_registry.py` and `tokenizer.py`; write a TOMIC context builder
over `PositionCache` and `MarketDataService`; non-streaming first (Dash callbacks cannot
stream; `dcc.Interval` polling or a WebSocket are the escalations); run the call off the
asyncio loop or switch to the async SDK clients. Two updates to it:

- **Decide whether the need exists before porting.** Nothing in the Argus or TOMIC
  records read for this assessment asks for an AI panel in TOMIC. The 2026-09-01
  concurrent-operation assessment treats TOMIC as a read-only monitor whose job for Argus
  positions is "visibility, not guidance"; an advisory LLM panel sits awkwardly beside
  that rule and would need its own "display-only, never a trading instruction" line.
- **If the need exists, §5.2 applies**: start from the current SDK with the Syvrona
  boundary pattern, not from the 2024 provider classes. The MVP estimate in §13.5 (one to
  two days, non-streaming) is still right; the "copy providers unchanged" step is not.

## 6. Is it worth the effort?

| Option | Days | What it buys | Verdict |
|---|---|---|---|
| **A. Full modernization and re-launch** | 5.5 to 8, then 15 to 30 for §3.8 | A current, hostable product in a category the market already judged | **No.** No buyer, no edge, ongoing cost. |
| **B. Archive-grade pass, then open-source, then the public Rails-Review sample** | 2.5 to 4, plus 1 to 2 for the sample | A verifiable "before" artifact for the method; proof of range; a sample of the paid deliverable; two or three content pieces that fit the plan's cadence; the keys out of the tree | **Yes, bounded.** This is the only option whose payoff lands in the current plan's 90-day window. |
| **C. Freeze as-is, private** | 0.5 (T0 is unconditional) | Nothing lost, nothing gained | Acceptable fallback, but the resume and site already point at a thing nobody can inspect. |

Choose B. Stop after T0 if, by the 2026-12-13 end of the go-to-market plan's Phase 2,
the content channels have produced no buyer-profile conversation: the sample review is
content, and the plan's own rule is to cut channels that produce none.

## 7. Open-sourcing: in Termondt Tech's interest?

**Yes, conditionally, and the conditions are the ones Argus already met.** The Argus
export (`argus/PUBLIC.md`; public since 2026-10-22; Apache-2.0 code, CC BY 4.0 documents;
a one-way export with `<!-- private-begin -->` markers, a check script that must report
zero hits, placeholders for hosts and accounts, secret scanning and push protection
enabled after the flip) is the template, and Syvrona is a far smaller case of it.

What makes Syvrona easier: no live account, no second strategy, no household data, no
vendor data under licence, a 5,000-line codebase. What makes it different:

- **The history question.** Argus started the public repository at one commit. For Syvrona
  the choice is a one-way export (same shape, same tooling idea, no history) or a flip of
  the existing repository with its 2024 to 2025 history. `git log --all` over the five env
  file paths shows none was ever committed. > **Unverified:** whether any early commit
  hardcoded a key, a webhook secret, a customer email or a price ID in source, a template
  or a release note. Run `gitleaks` or `trufflehog` over all refs before deciding. If it
  finds anything, export; if it finds nothing, a flip keeps the 2024 to 2025 commit record,
  which is itself part of the "before" evidence.
- **The issues.** 48 open issues and six stale branches are visible after a flip and not
  after an export. They are harmless (feature wishes and bugs), but they should be closed
  with a one-line "archived" comment or they read as an abandoned backlog.
- **Licensing.** Replace the proprietary `LICENSE` with Apache-2.0 (and fix the spelling on
  the way out); add `NOTICE` for `marked.min.js` (MIT) and `Sortable.min.js` (MIT);
  documents under CC BY 4.0 as Argus does. Drop `node_modules/tailwindcss`, which nothing
  references. The name "Syvrona" and the domain stay Termondt Tech's; the README states
  the product is retired.
- **Hard-coded identities.** `info@termondttech.com` in `app/utils.py` (public business
  address, fine to keep or move to config); `syvrona.com` in `base.html`'s canonical link
  and `static/sitemap.xml`; the droplet procedures in `docs/deployment.md` and
  `docs/digital_ocean_install.md` name no host or IP and can stay.
- **What stays out, always**: `.env*`, `.flaskenv*`, `app.log`, `instance/`, `.venv`,
  `node_modules/`, `db/`, and the dead files listed in T0.
- **The frame.** The public README's first paragraph says what this is: a retired
  subscription chat workspace, built in 2024 to 2025 with ordinary AI assistance and no
  rules file, published as the "before" artifact of the method that built Argus, with a
  review applied (link). Without that paragraph, publishing it hurts the brand it is
  meant to help.

Commercial downside: none found. The product is retired, the code embodies no edge, and
the buyer research notes that candid first-person accounts, not polished products, are
what the target channels reward. The upside is modest and specific: a buyer who reads the
Argus story can now also read the before-and-after, and the review sample exists.

## 8. Action items

Priority: **P0** safety or exposure, do regardless of any other decision · **P1** needed
for Option B · **P2** completes the archive-grade pass · **P3** optional, decision-gated.

Urgency: **[now]** · **[before publish]** · **[option B]** · **[if needed]**.

| ID | Priority | Urgency | Item | Owner |
|---|---|---|---|---|
| **AI-1** | **P0** | **[now]** | **Rotate every credential** present in `.flaskenv`, `.flaskenv.prod`, `app/.flaskenv.dev`, `.env`, `.env.prod`: OpenAI, Anthropic, Gemini, Stripe (live and test secret keys, webhook secrets), Mailgun, hCaptcha, `SECRET_KEY`, `SECURITY_PASSWORD_SALT`, MySQL passwords. Then delete the three `.flaskenv*` files and `app.log`, and keep a single `.env` (never committed) matching `.env.example`. | Rich |
| **AI-2** | **P0** | **[now]** | **Fix `.dockerignore`**: add `.git`, `.venv`, `.env*`, `.flaskenv*`, `app/.flaskenv.dev`, `node_modules`, `instance`, `docs`, `tests`, `*.db`, `*.sqlite`. Verify by building and listing `/app` inside the image. Until then, push no image anywhere. | agent, Rich reviews |
| **AI-3** | **P1** | **[before publish]** | Secret scan over all refs (`gitleaks detect --source . --log-opts="--all"` or `trufflehog git file://.`). Zero findings → a flip is allowed; any finding → one-way export with a new history. Record the result. | agent |
| **AI-4** | **P1** | **[option B]** | T1 dependency currency (§3.1), including the four SDK majors and the undeclared `requests`; direct deps in `pyproject.toml`, hash-pinned `requirements.txt`; suite green via `docker compose run --rm test`. | agent |
| **AI-5** | **P1** | **[option B]** | T2 model registry refresh (§3.3): Claude 5.5 IDs, verified OpenAI and Gemini IDs, every `fallback_model` a registry entry, `/answer` defaults to `DEFAULT_MODEL_KEY`, honest token counting. | agent |
| **AI-6** | **P1** | **[option B]** | Fix D1, D2, D3 (portable upsert or a dialect switch) and add the `FakeProvider` plus tests for `/answer`, quota 402, limiter 429 and the fallback chain. | agent |
| **AI-7** | **P1** | **[option B]** | T5 CI: SHA-pinned actions, `permissions: contents: read` on every workflow, `black`/`flake8` green, interpreter pinned to the image's version. | agent |
| **AI-8** | **P2** | **[option B]** | §3.7 docs truth: README status banner and accurate description, `LICENSE` text (Apache-2.0 if publishing) and spelling, `CHANGELOG.md` dates, `docs/roadmap.md` marked historical. | agent |
| **AI-9** | **P2** | **[option B]** | T3 hardening: cookie flags, Talisman/CSP, DOMPurify, Mailgun timeout, D8 datetimes, D11. | agent |
| **AI-10** | **P2** | **[if needed]** | T6 infrastructure: pin the base image, `mysql:8.4`, gunicorn `max_requests`, reconcile `mysql-conf` with the droplet size, scripted backup (closes #109). Only if the site will ever run again. | agent |
| **AI-11** | **P2** | **[before publish]** | Publication mechanics (§7): Apache-2.0 + `NOTICE` + CC BY 4.0 docs; public README frame; secret scanning and push protection after the flip; close the 48 issues with an "archived" comment; delete the six stale branches; remove the dead files. | agent, Rich flips |
| **AI-12** | **P3** | **[option B]** | The public Rails-Review sample over Syvrona (§4.2): findings table, a short constitution, three or four pinned invariants as tests, one write-up for the newsletter. | agent drafts, Rich signs |
| **AI-13** | **P3** | **[if needed]** | TOMIC AI panel: only on a stated need; non-streaming MVP; start from the current SDK with the `AIStreamer` boundary pattern (§5.3). | Rich decides |

## 9. Recommended end-state

1. **Keys rotated, image clean, history scanned** (AI-1 to AI-3), whatever else happens.
2. **A public `syvrona-ai` repository** (flip or export per AI-3), Apache-2.0, current
   dependencies and model list, green CI, 23-plus tests including the chat path, and a
   README whose first paragraph says it is retired and why it is published.
3. **A published review of it** in the Rails Review's shape, linked from the README and
   from `termondttech.com/syvrona`, and used as one or two newsletter editions.
4. **The private repository frozen** at the export commit, as Argus's is, with the
   `PUBLIC.md` table recording the mapping.
5. **No re-hosting**, no product roadmap, no TOMIC port until a need is written down.

## 10. What this assessment could not verify

Nothing was executed, so every "would fail" in §3.3 and §3.4 is read from the source,
not observed. Whether the pinned OpenAI and Gemini model IDs are still served. Whether
`stripe` 16.x still exposes `stripe.error`. Whether Flask-SQLAlchemy 3.1.1 works with
SQLAlchemy 2.1. The Docker Official Image's deprecation schedule for `mysql:8.0`.
Whether any template still posts to `/create-checkout-session` (D2). Whether the git
history contains any credential (AI-3 answers this). Whether the Stripe keys in the env
files are still active. The current state of the `syvrona.com` DNS, the droplet and the
Stripe account (not in scope; nothing was fetched). The TOMIC source itself was not read
for this assessment; §5.3 relies on `docs/architecture-reference-2026-06-30.md` §13 and
`argus/docs/tomic-argus-concurrent-operation-assessment.md`.
