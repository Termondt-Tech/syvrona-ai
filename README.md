# Syvnora

![Syvrona Logo](app/static/images/syvrona-logo-darktext-transparent.png)

Syvnora is an AI-powered technician assistant platform, built with Laravel and designed to connect with OpenAI, internal knowledge bases, and third-party systems like Drupal. It’s developed and maintained by [Termondt Tech](https://termondttech.com).

---

## 🚀 Tech Stack

- Python
- Flask
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
docker exec -it syvnora-ai-web bash
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
