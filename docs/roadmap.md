# Syvrona Development Roadmap

This roadmap outlines the modular, incremental delivery of **Syvrona**, an AI-powered web app built with **Python (Flask)**, **Docker**, and **MySQL**, featuring streaming chat and extensible AI integrations. The app supports user authentication and a subscription-based model.

---

## 🚧 Upcoming & In Progress

### Track 1: Core Product Value (Highest Priority)

- Prompt builder
- File upload/document library + chat with files
- Image generation in chat
- AI-powered conversation organization (tagging, summaries, export)
- User dashboard, notifications
- **Customizable AI Agents:** Allow users to create personalized AI agents that can be trained on specific data or behavior preferences, including voice tone, writing style, or domain-specific knowledge.
- **Automated Research Tool:** Offer a service where the AI can scan multiple sources, summarize findings, and provide insights on specific topics, giving users quick access to high-quality research.

### Track 2: Platform & Scaling (Support/Parallel)

- Secret management
- Resilience
- Database refactor for scaling

### Track 3: Go-To-Market & Growth (Time Sensitive)

- Blog & content marketing for each release
- Social/post promotion
- **Google Ads campaigns (use \$1000 credit by Aug 12, 2025)**
- Feedback surveys, onboarding improvements

---

**Usage:**

- Break each phase into GitHub issues/tasks

---

## Feature to Release Map

[Feature to Release Map](./feature_release_map.md)

## ✅ Completed Phases

### ✅ Phase 1: Core Setup + Basic Chat (MVP Skeleton)

- Flask scaffold with Blueprint structure
- Dockerized development environment
- MySQL backend for persistence
- User registration, login, logout (Flask-Login)
- Role distinction: Admin vs Regular user
- Chat UI with static OpenAI response
- Store conversations/messages in MySQL

---

### ✅ Phase 2: Streaming Chat + Conversational Memory

- Server-Sent Events (SSE) for real-time chat
- Store and retrieve conversation history
- Inject prior messages into OpenAI prompt
- Allow model selection per conversation

---

### ✅ Phase 3: Subscriptions + Stripe Billing

- Stripe Checkout and Billing Portal integration
- Free tier with limited access
- Paid plans unlock advanced features
- Admin overrides for Termondt Tech staff

---

### ✅ Phase 4: Multi-Provider, Multi-Model Support

- Abstract AI logic into service layer
- Allow user to select model/provider
- Store provider/model with each conversation
- Extendable for future providers

---

### ✅ Phase 5: Stripe Subscription Implementation, Message Tagging, Account Security

- Stripe subscription enforcement
- Message tagging (admin, system)
- Forgot password and reset flows
- Free trial feature flag
- Improved email templates

---

### ✅ Phase 6: Ticketing, Notifications, Admin & Dashboard Enhancements

- Support ticket subsystem (user-to-staff private tickets)
- Admin dashboard for ticket management
- Transactional email notifications for ticketing
- Spam protection (hCaptcha) for signup/tickets
- In-app notification subsystem (dashboard & admin)
- Notification preferences

---
