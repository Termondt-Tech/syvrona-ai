# Syvrona

![Syvrona Logo](app/static/images/syvrona-logo-darktext-transparent.png)

**Retired. Not hosted, not maintained, published as an archive.**

Syvrona was a subscription chat workspace for thinking and writing with AI: streaming chat
with conversation memory, a prompt library and prompt chains, tagging, a choice of OpenAI,
Anthropic and Google Gemini models, and Stripe billing with per-plan rate limits and monthly
token quotas. Termondt Tech built and launched it in 2024 and 2025, with ChatGPT as a coding
assistant and no written rules for that assistant. It is no longer hosted and has no users.

It is public as the "before" picture of the method behind
[Argus](https://github.com/Termondt-Tech/argus-platform), which was built later by directing
AI coding agents under written rules. The
[2026 assessment](docs/syvrona-modernization-and-value-assessment-2026-11-05.md) read the
code as it stood when the product stopped. In November 2026 it was brought up to date
without being relaunched: current dependencies and models, and the twelve defects the
assessment found plus ten more found on the way, each fixed with a test. The
[change record](docs/syvrona-modernization-change-record-2026-11-06.md) lists every change and how it was checked.
It is still not hosted, and no live model call has been made since the keys were revoked.
More at [termondttech.com/syvrona](https://termondttech.com/syvrona).

Every API key the app ever used has been revoked. No credential is in the code or the git
history: see the [secret-scan record](docs/git-history-secret-scan-2026-11-06.md).

---

## Documentation

- [Modernization and value assessment, 2026-11-05](docs/syvrona-modernization-and-value-assessment-2026-11-05.md)
- [Modernization change record, 2026-11-06](docs/syvrona-modernization-change-record-2026-11-06.md)
- [Architecture reference, 2026-06-30](docs/architecture-reference-2026-06-30.md)
- [Git-history secret scan, 2026-11-06](docs/git-history-secret-scan-2026-11-06.md)
- [Claude Code guide (CLAUDE.md)](CLAUDE.md)
- [Best Practices](docs/best_practices.md)
- [Deployment Guide](docs/deployment.md) and [DigitalOcean Install Guide](docs/digital_ocean_install.md), historical
- [Product Roadmap](docs/roadmap.md), historical
- [Release Notes](docs/releases/) and [Changelog](CHANGELOG.md)

---

## Tech stack

- Python 3.13, Flask 3.1, SQLAlchemy 2.1, Alembic migrations
- MySQL 8.0, Redis (rate limiting), Docker Compose, Gunicorn
- OpenAI (GPT-6), Anthropic (Claude 5.5) and Google Gemini (3.5 to 4) behind one
  streaming endpoint
- Dependencies declared in `pyproject.toml`, installed from hash-pinned locks
- Stripe subscriptions, Mailgun email, optional hCaptcha
- Jinja2 templates with inline JavaScript; no frontend build

---

## Running it locally

You need your own keys. A provider's key is needed only when one of its models is used,
and Stripe only for billing. Every variable is listed, without values, in `.env.example`.

```bash
git clone https://github.com/Termondt-Tech/syvrona-ai.git
cd syvrona-ai
cp .env.example .env                                   # fill in your own values
docker compose up -d --build                           # app at http://localhost:5001
docker exec -it syvrona-ai-web-1 flask db upgrade      # create the schema from empty
```

Chat requires an active subscription or an admin account (`app/decorators.py`).

Run the test suite, on SQLite inside the test image, as CI does:

```bash
docker compose build test && docker compose run --rm test
```

---

## Release history

Releases v1.0.0 to v1.4.8 were cut between May and August 2025 from Git tags. From v1.4.3
on, Release Drafter built the notes from merged pull requests, and an autolabeler tagged
pull requests by title and changed files. See [.github/release-drafter.yml](.github/release-drafter.yml),
[.github/autolabeler.yml](.github/autolabeler.yml), [docs/releases/](docs/releases/) and
[CHANGELOG.md](CHANGELOG.md).

---

## Contributing

This repository is an archive. Issues and pull requests are not monitored. Fork it freely
under the licence.

---

## Licence

Code under the Apache License 2.0 (`LICENSE`, `NOTICE`); documents under Creative Commons
Attribution 4.0 (`LICENSE-docs`). The two bundled JavaScript libraries keep their MIT
licences (`THIRD_PARTY_LICENSES`). The Syvrona name and logo are not licensed as marks.

---

## Author

**[Rich Termondt](https://termondttech.com)**, Founder and Principal Architect, Termondt Tech LLC

[![Pytest (Docker Compose)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml) [![Python Lint](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml) [![Docker Build](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml) [![Secret Scan](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/secret-scan.yml)
