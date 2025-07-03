# Syvnora

![Syvrona Logo](app/static/images/syvrona-logo-darktext-transparent.png)

Syvnora is an AI-powered technician assistant platform, built with Flask and designed to connect with OpenAI, internal knowledge bases, and third-party systems. It’s developed and maintained by [Termondt Tech](https://termondttech.com).

---

## 🚀 Tech Stack

- Python 3.9
- Flask 3
- Docker
- Sqlite
- OpenAI API integration

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

## 📄 License

This project uses a proprietary license and is the intellectual property of Termondt Tech LLC.  
See the [LICENSE](LICENSE) file for full terms.

---

## 🤝 Maintained By

**[Rich Termondt](https://termondttech.com)**  
Founder & Principal Architect at Termondt Tech LLC

[![Pytest (Docker Compose)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/test.yml) [![Python Lint](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/python-lint.yml) [![Docker Build](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Termondt-Tech/syvrona-ai/actions/workflows/docker-build.yml)
