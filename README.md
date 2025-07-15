# Syvrona

![Syvrona Logo](app/static/images/syvrona-logo-darktext-transparent.png)

Syvrona is an AI-powered technician assistant platform, built with Flask and designed to connect with OpenAI, internal knowledge bases, and third-party systems. It’s developed and maintained by [Termondt Tech](https://termondttech.com).

---

## 🚀 Tech Stack

- Python 3.12
- Flask 3.1.1
- Docker
- MySQL
- OpenAI API integration
- Anthropic API integration

---

## 🧪 Local Development Setup

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

## 🛠️ Automated Releases & PR Labeling

This repository uses **automated release note generation** and **pull request labeling** to streamline contributions and change tracking:

- **Release Drafter:**  
  Every time a pull request is merged, a draft release is automatically updated with categorized release notes based on PR titles, labels, and referenced issues.  
  👉 To help keep release notes clear, please give your pull requests meaningful titles and descriptions, and reference any related issues (e.g., “Fixes #42”).

- **Probot Autolabeler:**  
  Pull requests are automatically labeled based on their content (files changed, keywords in the title/body, etc.).  
  👉 You can customize these labels by editing `.github/autolabeler.yml` in the repo. Existing labels include: `bug`, `enhancement`, `documentation`, `question`, and more.

### Contributor Guidelines

Help us keep releases organized:

- **Write clear pull request titles and descriptions**
- **Reference issues** using `Fixes #issue_number`
- **Check your PR labels** (they may be applied automatically)

For more information, see the [`.github/release-drafter.yml`](.github/release-drafter.yml) and [`.github/autolabeler.yml`](.github/autolabeler.yml) configuration files.

## 📄 License

This project uses a proprietary license and is the intellectual property of Termondt Tech LLC.  
See the [LICENSE](LICENSE) file for full terms.

---

## 🤝 Maintained By

**[Rich Termondt](https://termondttech.com)**  
Founder & Principal Architect at Termondt Tech LLC

[![Pytest (Docker Compose)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml) [![Python Lint](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml) [![Docker Build](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml)
