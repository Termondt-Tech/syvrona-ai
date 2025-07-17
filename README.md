# Syvrona

![Syvrona Logo](app/static/images/syvrona-logo-darktext-transparent.png)

Syvrona is an AI-powered technician assistant platform, built with Flask and designed to connect with OpenAI, internal knowledge bases, and third-party systems. It’s developed and maintained by [Termondt Tech](https://termondttech.com).

---

## 📚 Documentation

- [Best Practices](docs/best_practices.md)
- [Deployment Guide](docs/deployment.md)
- [DigitalOcean Install Guide](docs/digital_ocean_install.md)
- [Product Roadmap](docs/roadmap.md)
- [Release Notes](docs/releases/)
- [Changelog](CHANGELOG.md)
  
---

## 🚀 Tech Stack

- Python 3.12
- Flask 3.1.1
- Docker
- MySQL
- OpenAI API integration
- Anthropic API integration

---

## 🧑‍💻 Local Development Setup

```bash
# Clone the repository
git clone https://github.com/Termondt-Tech/syvrona-ai.git
cd syvrona-ai

# Spin up local containers
docker-compose up -d --build

# Enter the app container
docker exec -it syvrona-ai-web-1 bash

# Migrate database changes - assuming flask db init has already been run
flask db migrate -m "migration comments..."
flask db upgrade

```

App runs at: [http://localhost:5001](http://localhost:5001)

---

## 🔄 Automated Releases & PR Labeling

This repository uses **automated release note generation** and **pull request labeling** to streamline contributions and change tracking:

- **Release Drafter:**  
  Automatically generates draft release notes from merged PRs.  
  ➤ Please use clear PR titles, descriptions, and reference issues (e.g., “Fixes #42”).

- **Probot Autolabeler:**  
  PRs are auto-labeled by file changes and keywords.  
  ➤ Customize labels in `.github/autolabeler.yml`. Labels include: `bug`, `enhancement`, `documentation`, `question`, etc.

See [.github/release-drafter.yml](.github/release-drafter.yml) and [.github/autolabeler.yml](.github/autolabeler.yml) for details.

### 🧑‍🤝‍🧑 Contributor Guidelines

Help us keep releases organized:

- Use descriptive PR titles and descriptions.
- Reference related issues (`Fix #123`).
- Check PR labels before merging.

## 📄 License

This project uses a proprietary license and is the intellectual property of Termondt Tech LLC.  
See the [LICENSE](LICENSE) file for full terms.

---

## 🤝 Maintained By

**[Rich Termondt](https://termondttech.com)**  
Founder & Principal Architect at Termondt Tech LLC

[![Pytest (Docker Compose)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml) [![Python Lint](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml) [![Docker Build](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml)
