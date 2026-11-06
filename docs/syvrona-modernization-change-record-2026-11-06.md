# Syvrona modernized: current dependencies and models, 22 defects fixed, live calls unverified, 2026-11-06

**Type: change record. Not normative.** It records what the 2026-11-06 modernization
changed and how each change was checked. It changes no code by itself; the code is the
record of truth, and `CLAUDE.md` carries the current-state rules.

Verified against source: syvrona-ai `master` @ `90a30d8` plus the working-tree change this
document describes. Scope: the assessment's AI-4 (dependency currency), AI-5 (model
registry) and AI-6 (defects and tests), with AI-7's lint and pins. AI-9 hardening and AI-10
infrastructure were not in scope.

## 1. The answer

- **Every dependency is current, under a seven-day cooldown.** Python 3.12 → 3.13.17; the
  four SDK majors moved (openai 2 → 3, anthropic 0.73 → 2, google-genai 1 → 2, stripe 13 → 16).
  Direct dependencies now live in `pyproject.toml`, and both images install from
  hash-pinned locks.
- **The model registry is current.** Six of its ten IDs were retired, shut down or
  deprecated. It now offers GPT-6, Claude 5.5 and Gemini 3.5 to 4, and it validates itself
  at import.
- **D1 to D12 are fixed, and so are ten more defects found while fixing them.** One is a
  security bug: `/answer` streamed another user's conversation to the model on request
  (D13). Two meant a fallback could never fire (D15) or every Claude 5.5 call would fail
  (D16).
- **The chat path has tests for the first time.** The suite grew from 23 to 118 tests. It
  passes on SQLite, inside the test image and on MySQL 8.0.46.
- **No live provider call was made.** Every key was revoked on 2026-11-06. The new model
  IDs, limits and parameter rules come from the providers' own documentation, read the same
  day. A smoke test with fresh keys is the first thing to do before any hosting (MOD-1).

## 2. Dependencies

The lock excludes anything published after 2026-10-30, seven days before it was cut. That
holds back google-genai 3.0.0 (released 2026-11-06), openai 3.46 and anthropic 2.6.

| Package | Was | Now | Note |
|---|---|---|---|
| Python (image) | `3.12-slim`, unpinned | `3.13.17-slim-trixie` | Matches the local `.venv`; CI lint now runs 3.13 too. |
| `openai` | 2.8.1 | 3.41.0 | Typed Responses events; see D10. |
| `anthropic` | 0.73.0 | 2.3.0 | Sends API version 2026-10-21; `temperature`, `top_p` and `top_k` are gone from the SDK (D16). |
| `google-genai` | 1.51.0 | 2.34.0 | Raises `google.genai.errors.APIError`, not `google.api_core` exceptions (D15). |
| `google-api-core` | 2.28.1 | removed | Only imported for the exceptions the SDK never raised. |
| `stripe` | 13.2.0 | 16.1.0 | `stripe.error.SignatureVerificationError` → `stripe.SignatureVerificationError`. |
| `SQLAlchemy` | 2.0.44 | 2.1.6 | Works with Flask-SQLAlchemy 3.1.1 (the assessment's open question); all 17 legacy `Query.get`/`get_or_404` calls replaced. |
| `gunicorn` | 23.0.0 | 26.2.0 | Config unchanged. |
| `cryptography` | 44.0.3 | 50.0.2 | Now declared through `PyMySQL[rsa]`. |
| `redis` | 7.0.1 | 7.4.1 | Capped below 8 by `limits[redis]`. |
| `requests` | undeclared | 2.34.2 | Imported directly by `app/utils.py`. |
| Flask, Werkzeug, Flask-WTF, Flask-Limiter | 3.1.2, 3.1.3, 1.2.2, 4.0.0 | 3.1.3, 3.1.9, 1.3.0, 4.1.1 | |
| tiktoken, PyMySQL, python-dotenv, certifi, pytest | 0.12.0, 1.1.2, 1.1.0, 2025.4.26, 9.0.1 | 0.14.0, 1.2.3, 1.2.4, 2026.10.23, 9.2.0 | |

The `Dockerfile` now has two stages. `test` installs `requirements-dev.txt` and is what
compose and CI run. `runtime` installs `requirements.txt`, so pytest no longer ships to
production. Both stages bake in tiktoken's `o200k_base` file at build time, so the server
never downloads it while answering a request. The lock command is in `CLAUDE.md`.

## 3. Model registry

Sources: each provider's models overview, deprecations page and latest-model or migration
guide (developers.openai.com, platform.claude.com, aistudio.google.com), read 2026-11-06.

| Old ID | Status on 2026-11-06 | Replaced by |
|---|---|---|
| `gpt-5.2-chat-latest` (the default) | Retired 2026-08-10 | `gpt-6.1-sol` (the new default) |
| `gpt-5.1-2025-11-13` | Deprecated; shuts down 2027-04-01 | `gpt-6-astra` |
| `gpt-5.1-codex` | Retired 2026-07-23 | `gpt-6-luna` |
| `claude-sonnet-4-5-20250929` | Deprecated; retires 2026-11-30 | `claude-sonnet-5-5` |
| `claude-opus-4-5-20251101` | Legacy | `claude-opus-5-5` |
| `claude-haiku-4-5-20251001` | Active, past its stated window | `claude-haiku-5-5` |
| `gemini-3-pro-preview` | Shut down 2026-03-09 | `gemini-4-argon` |
| `gemini-2.5-pro` | Deprecated; auto-routes from 2026-12-01 | `gemini-3.8-flash` |
| `gemini-2.5-flash` | Deprecated; auto-routes from 2026-12-01 | `gemini-3.5-flash-lite` |
| `gemini-2.0-flash` (a fallback target) | Shut down 2026-06-01 | not needed |

Each provider has a flagship → balanced → fast fallback chain, and every hop is a registry
entry. Limits are the documented ones: 1,050,000 / 128,000 tokens for GPT-6,
1,000,000 / 128,000 for Claude 5.5, and 1,048,576 shared / 65,536 for Gemini.

Every entry's `generation_config` is empty, because current models refuse sampling
settings. Claude 5.5 answers 400 to `temperature`, `top_p` or `top_k`. Gemini 3.6+ and 4
ignore them and send deprecation headers. GPT-6 accepts `temperature`/`top_p` only when
`reasoning_effort` is `"none"`, which Astra and 6.1 Sol do not support.
`model_registry.py::validate_registry` turns each rule into a startup error. The unused
`PROFILE_OVERRIDES`, `build_generation_config` and `app/model_limits.py` are deleted.

> **Unverified:** whether `gemini-4-argon` serves `generate_content_stream`. Google's
> examples for it use only the newer Interactions API. A 404 there falls back to
> `gemini-3.8-flash`.

## 4. Defects fixed

D1 to D12 are the assessment's (§3.4). D13 to D22 were found while fixing them.

| # | Anchor | What was wrong | Fix | Test |
|---|---|---|---|---|
| D1 | `services/conversation.py::get_conversation` | Raised on a missing row, so every conversation route returned 500 instead of 404. | Returns `None`; `get_user_conversation` combines lookup and ownership. | `test_conversation_routes.py` |
| D2 | `billing.py::create_checkout_session` | `url_for("profile")` built no URL. | `auth.profile`. Also: the price must be one of the configured plans, and Stripe errors no longer reach the client. | `test_billing.py::test_checkout_*` |
| D3 | `services/ai_streamer.py::_inc_usage` | MySQL-only upsert; the chat path could not be tested. | `models.py::add_usage_tokens`, one atomic statement per dialect (MySQL, SQLite, PostgreSQL). | `test_ai_streamer.py` on SQLite and MySQL |
| D4 | `AIStreamer.chat` | The user turn was saved before the call, so a failure left it orphaned and a retry duplicated it. | Both turns and the usage are saved in one commit, only on success. | `test_*failure*`, `test_client_disconnect_*` |
| D5 | all providers | No context-window management. | `fit_history` trims oldest first to `(window − max output) × 0.75`; an oversized prompt is a 413. | `test_fit_history_*`, `test_prompt_over_budget_is_a_413` |
| D6 | `model_registry.py` | A fallback pointed at an ID outside the registry. | Every chain is validated at import. | `test_model_registry.py` |
| D7 | `chat.py::answer` | The default model was `gpt-3.5-turbo`. | `DEFAULT_MODEL_KEY`; an unknown model is a 400. | `test_default_model_is_the_registry_default` |
| D8 | `billing.py`, `services/signup.py`, `admin_routes.py` | Naive local-time datetimes. | Aware UTC everywhere. | `test_webhook_stores_subscription_dates_in_utc`, run as a Chicago host |
| D9 | `extensions.py` | `limiter` was defined twice, and a Redis client was never used. | One limiter; storage comes from `RATELIMIT_STORAGE_URI`. | `test_rate_limit_is_a_429` |
| D10 | `openai_provider.py` | Three heuristic chunk parsers; in-stream errors were ignored; only `model_not_found` triggered a fallback. | Typed Responses events; `error` and `response.failed` raise `ProviderError`; HTTP 403, 404 and 429 raise `ModelAccessError`. | `test_providers.py::test_openai_*` |
| D11 | `utils.py::send_mailgun_message` | No timeout. | `(5, 15)` second timeout; failures are logged and return `False` instead of breaking signup. | `test_utils.py` |
| D12 | `limits.py::enforce_token_quota` | Issue #124 asked for an index. | Not needed: `EXPLAIN` on MySQL 8.0.46 shows a `const` read on `uix_usage_month`. | §5 |
| **D13** | `chat.py::answer` | **Security.** No ownership check on `conversation_id`. Any subscriber could add turns to another user's conversation and have the model read its whole history back to them. | 404 unless the conversation is the caller's; POST only; input validated. | `test_another_users_conversation_is_a_404_and_untouched` |
| D14 | providers + `AIStreamer` | Every prompt reached the model twice: it was saved first, then re-read with the history, then appended again. | History is loaded once before anything is saved. | `test_prompt_is_sent_exactly_once_with_prior_history` |
| D15 | `gemini_provider.py` | It caught `google.api_core` exceptions, which google-genai never raises, so the Gemini fallback could not fire. | `google.genai.errors.APIError` with `.code`. | `test_gemini_status_mapping` |
| D16 | `anthropic_provider.py` | It sent `temperature` (a 400 on Claude 5.5, and gone from SDK 2.x) and read `.text` from every delta (thinking deltas have none). | No sampling; text deltas only. | `test_anthropic_request_and_text_only` |
| D17 | `models.py`, `chat.py::latest_messages` | Ordering by `created_at` alone; MySQL stores seconds, so a fast reply could sort before its question. | `(created_at, id)` everywhere. | `test_same_second_rows_*`, `test_latest_orders_*` |
| D18 | `migrations/` | The chain could not build an empty database: its root assumed a `user` table made by `db.create_all()`. | `baseline_2025_05` creates the May 2025 tables. | `flask db upgrade` + `flask db check` on MySQL (§5) |
| D19 | `app.py` | `load_dotenv()` ran after the import that reads the environment. | Load first. | none (startup order) |
| D20 | `services/ai_streamer.py::ProviderRegistry` | All three SDK clients were built on every request; `OpenAI()` fails without a key, so one missing key broke every model. | Built on first use, one per process. | `test_provider_registry_*` |
| D21 | `AIStreamer.chat` fallback | Each fallback attempt saved the user turn again. | One save per turn, naming the model that answered. | `test_model_access_error_falls_back_along_the_chain` |
| D22 | `tokenizer.py` | A user message containing `<|endoftext|>` raised inside tiktoken. | Special tokens are counted as text. | `test_tokenizer.py` |

## 5. Verification

| Check | Result |
|---|---|
| black 26.10.1, flake8 7.5.0 (the CI pins) | Clean |
| Suite, Python 3.13.12 venv, `-X dev`, resource and unraisable warnings as errors | 118 passed |
| Suite in the `test` image (Python 3.13.17), as CI runs it | 118 passed, no warnings |
| Suite on MySQL 8.0.46 via `TEST_DATABASE_URL` | 118 passed |
| `flask db upgrade` on an empty MySQL 8.0.46, then `flask db check` | 15 revisions applied; "No new upgrade operations detected" |
| D12: `EXPLAIN` of the quota lookup | `type=const`, `key=uix_usage_month`, `rows=1` |
| Mutation check: six fixes undone one at a time (D2, D8, D13, D14, D16, D17) | Each catching test failed |
| `runtime` image | Python 3.13.17, user `appuser`, no pytest, tiktoken data present |
| gitleaks over the working tree and all history | No leaks |

The Docker VM's disk was full during verification. Untagged images and the oldest build
cache were pruned to free it, leaving the newest 6 GB of cache. No volume was touched.

## 6. Action items

| ID | Priority | Urgency | Item | Owner |
|---|---|---|---|---|
| **MOD-1** | **P1** | **[before any hosting]** | Smoke test with fresh keys. Send one turn on each of the nine models, force one fallback per provider, and check one Stripe webhook against the account's API version. | Rich, agent assists |
| **MOD-2** | **P1** | **[now]** | Commit and push. CI then runs the 3.13 lint, the `test` stage and the `runtime` build on GitHub for the first time. | Rich |
| MOD-3 | P2 | [after 2026-11-13] | Re-lock once the cooldown passes. That brings in google-genai 3.x (a major: review its changelog), `python:3.13.18`, openai 3.46 and anthropic 2.6. | agent |
| MOD-4 | P2 | [if hosted] | AI-9, still open: session cookie flags, CSP headers, and DOMPurify around `marked` output (the stored-XSS path in `chat.html`). | agent |
| MOD-5 | P2 | [if hosted] | AI-10, still open: MySQL 8.4, gunicorn `max_requests`, `mysql-conf` sizing, scripted backups. | agent |
| MOD-6 | P3 | [if needed] | A Gemini Interactions API adapter, if MOD-1 shows Argon needs it. | agent |
| MOD-7 | P3 | [option] | Count quotas from provider-reported usage instead of local estimates. This is a product decision: real input counts include the whole history. | Rich decides |
| MOD-8 | P3 | [at the next tag] | Release note and `CHANGELOG.md` line, if this is tagged. `pyproject.toml` says `1.5.0.dev0`. | Rich |

## 7. What this could not verify

- No provider was called: keys are revoked. Adapters are tested against fake SDK clients
  that use each SDK's real event and exception types.
- Model IDs, limits and parameter rules come from documentation, not from an API listing.
  Unconfirmed: Argon on `generateContent`; whether OpenAI rejects or ignores sampling
  settings when effort is not `none`; whether Gemini rejects or ignores `candidate_count`.
- The web stack was not started and the UI was not exercised in a browser. The streaming
  client in `chat.html` is unchanged, and the response shape and headers it reads are
  tested.
- GitHub Actions has not run this change.
- Stripe webhook payloads were tested with the item-level `current_period_*` fields the
  code reads. The live account's API version was not checked.
