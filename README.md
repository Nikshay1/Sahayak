# 🏥 Sahayak - Zero-UI Agentic AI for Elderly Care

<div align="center">

![Sahayak Logo](docs/images/logo.png)

**Empowering elderly users to order medicines through simple voice interaction**

[![CI/CD](https://github.com/Nikshay1/Sahayak/actions/workflows/ci.yml/badge.svg)](https://github.com/Nikshay1/Sahayak/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [The Solution](#-the-solution)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Demo](#-demo)
- [API Documentation](#-api-documentation)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Contributing](#-contributing)

---

## 🎯 The Problem

Digital adoption has left the elderly behind. While interfaces have evolved from keyboard to touch, the cognitive load of apps, authentication flows (OTPs), and navigation remains too high for the 60-90 age demographic.

**The "Grandmother Test":** Can a non-technical senior successfully order medicine without calling their children for help?

## 💡 The Solution

**Sahayak** is a **Zero-UI Agentic AI** that lives on a phone line. The user speaks naturally, and the agent executes digital tasks on their behalf using a managed, prepaid wallet.

```
📞 User calls Sahayak
↓
🗣️ "Beta, my calcium medicines are finished"
↓
🤖 AI understands intent, checks history
↓
💬 "I see you usually order Shelcal 500. A strip costs ₹120. Shall I order?"
↓
👵 "Yes, please"
↓
✅ Order placed, wallet debited, SMS sent
```

## ✨ Key Features

### 🎙️ Voice-First Intake
- Telephony/WhatsApp audio as the only input
- 1.5-second silence detection for elderly speech patterns
- Hindi/English dialect support via OpenAI Whisper

### 🧠 Deterministic Intent
- GPT-4o powered intent extraction
- Strict JSON schema output
- Confidence-based clarification flows
- "Safe Refusal" below 90% confidence

### 💰 Trust Ledger
- Prepaid closed-loop wallet
- No OTPs or UPI PINs during calls
- Double-entry ledger pattern
- ₹2000 per-transaction cap
- Automatic refunds on API failures

### 🔒 Privacy & Safety
- PII redaction before LLM calls
- End-to-end audit logging
- Emergency detection (redirects to 112)
- Caregiver notifications

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       SAHAYAK ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📞 Telephony Layer                                             │
│   ├── Twilio Voice Webhooks                                     │
│   ├── WhatsApp Business API                                     │
│   └── Audio Streaming & Buffering                               │
│   ↓                                                             │
│  🎤 Voice Processing                                            │
│   ├── OpenAI Whisper (STT)                                      │
│   ├── Silence Detection (1.5s threshold)                        │
│   └── Transcription Enhancement                                 │
│   ↓                                                             │
│  🧠 Intent Engine                                               │
│   ├── GPT-4o Intent Parsing                                     │
│   ├── Medicine Resolution (user history)                        │
│   └── Confidence Scoring & Clarification                        │
│   ↓                                                             │
│  ⚙️ Execution Orchestrator                                      │
│   ├── Wallet Check & Lock                                       │
│   ├── Voice Confirmation                                        │
│   ├── Pharmacy API Adapter                                      │
│   └── Auto-Refund on Failure                                    │
│   ↓                                                             │
│  💾 Data Layer                                                  │
│   ├── PostgreSQL (ACID compliant)                               │
│   ├── Double-Entry Ledger                                       │
│   └── Audit Logs                                                │
│   ↓                                                             │
│  📱 Notifications                                               │
│   ├── SMS Confirmation                                          │
│   ├── WhatsApp Messages                                         │
│   └── Caregiver Alerts                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)
- OpenAI API Key
- Twilio Account (for telephony)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/Nikshay1/Sahayak.git
cd Sahayak

# Copy environment file
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start all services
docker-compose up -d

# Seed demo data
docker-compose exec app python scripts/seed_demo_user.py

# View logs
docker-compose logs -f app
```

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/Nikshay1/Sahayak.git
cd Sahayak

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL database
createdb sahayak_db

# Copy and configure environment
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Seed demo data
python scripts/seed_demo_user.py

# Start the server
uvicorn src.main:app --reload
```

### Expose Webhooks (Development)

```bash
# Using ngrok
ngrok http 8000

# Update Twilio webhook URLs with ngrok URL
# Voice URL: https://your-ngrok-url.ngrok.io/webhooks/twilio/voice/incoming
```

---

## 🎬 Demo

### Run the Demo Simulation

```bash
# Interactive demo
python scripts/demo_simulation.py

# Select scenario:
# 1. Full Order Flow (Grandmother Test)
# 2. Balance Check
# 3. Clarification Flow
# 4. Run All Demos
```

### Demo Script (The "Grandmother Test")

| Step | Speaker | Dialogue |
|------|---------|----------|
| 1 | 👵 User | (Dials number) "Hello? Is this Sahayak?" |
| 2 | 🤖 AI | "Namaste Sunita. Yes, I am here. How can I help you today?" |
| 3 | 👵 User | "Beta, my calcium medicines are finished. Can you send a new strip?" |
| 4 | 🤖 AI | "I can see you usually order Shelcal 500. A strip of 15 costs 120 rupees. Shall I order it to your home in Indiranagar?" |
| 5 | 👵 User | "Yes, please." |
| 6 | 🤖 AI | "Done. I have paid 120 rupees from your wallet. Your new balance is 880 rupees. The chemist will deliver it by 5 PM." |

### Test via API

```bash
# Parse intent from text
curl -X POST "http://localhost:8000/api/voice/parse-intent?text=mujhe%20calcium%20ki%20dawai%20chahiye&phone_number=9876543210"

# Simulate full call
curl -X POST "http://localhost:8000/api/voice/simulate-call" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9876543210", "transcript": "Beta, meri calcium ki dawai khatam ho gayi"}'

# Check wallet balance
curl "http://localhost:8000/api/wallet/balance/9876543210"

# Top up wallet
curl -X POST "http://localhost:8000/api/wallet/topup" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9876543210", "amount": 500}'
```

---

## 📚 API Documentation

Once the server is running, access the interactive API docs:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhooks/twilio/voice/incoming` | `POST` | Handle incoming calls |
| `/webhooks/twilio/voice/process` | `POST` | Process voice input |
| `/webhooks/whatsapp/message` | `POST` | Handle WhatsApp messages |
| `/api/wallet/balance/{phone}` | `GET` | Get wallet balance |
| `/api/wallet/topup` | `POST` | Add money to wallet |
| `/api/voice/parse-intent` | `POST` | Test intent parsing |
| `/api/voice/simulate-call` | `POST` | Simulate a call |
| `/health` | `GET` | Health check |

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | Required for calls |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | Required for calls |
| `TWILIO_PHONE_NUMBER` | Twilio phone number | Required for calls |
| `SILENCE_THRESHOLD_SECONDS` | Silence detection threshold | 1.5 |
| `CONFIDENCE_THRESHOLD` | Intent confidence threshold | 0.85 |
| `SAFE_REFUSAL_THRESHOLD` | Refusal threshold | 0.90 |
| `MAX_TRANSACTION_AMOUNT` | Max transaction in ₹ | 2000 |

### Supported Intents

| Intent | Description | Example Phrases |
|--------|-------------|-----------------|
| `ORDER_MEDICINE` | Order medicines | "Mujhe dawai chahiye", "Send calcium tablets" |
| `CHECK_BALANCE` | Check wallet balance | "Kitne paise hain", "What's my balance" |
| `ORDER_STATUS` | Check order status | "Mera order kahan hai" |
| `UNKNOWN` | Unrecognized intent | Triggers clarification |

### Unsupported Actions (By Design)

- Emergency services (redirects to 112)
- Banking transfers
- General chat

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_intent_engine.py -v

# Run specific test
pytest tests/test_wallet.py::TestWalletLedger::test_check_and_lock_success -v
```

### Test Coverage Goals

- Intent Engine: 90%+
- Wallet Ledger: 95%+
- Orchestrator: 85%+
- Overall: 80%+

---

## 🚢 Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Configure real Twilio credentials
- [ ] Set up PostgreSQL with proper backups
- [ ] Configure SSL/TLS
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Configure rate limiting
- [ ] Set up log aggregation

### Deploy with Docker

```bash
# Build production image
docker build -t sahayak:prod .

# Run with production config
docker run -d \
  --name sahayak \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e OPENAI_API_KEY=... \
  -e ENVIRONMENT=production \
  sahayak:prod
```

### Kubernetes (Coming Soon)

Helm charts and Kubernetes manifests will be added for production deployments.

---

## 📊 Monitoring

### Key Metrics to Track

- Call completion rate
- Intent detection accuracy
- Average call duration
- Wallet transaction success rate
- API failure rate
- Refund frequency

### Log Structure

All calls generate structured logs:

```json
{
  "call_id": "call_12345",
  "input_audio_url": "s3://...",
  "transcribed_text": "Send Crocin",
  "intent_detected": "ORDER_MEDICINE",
  "wallet_status": "APPROVED",
  "execution_status": "SUCCESS"
}
```

---

## 🤝 Contributing

We welcome contributions! Please see our Contributing Guide.

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Run linting
black src tests
isort src tests
flake8 src tests
```

### Code Style

- Use Black for formatting
- Use isort for import sorting
- Follow PEP 8 guidelines
- Write docstrings for all functions
- Add type hints

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- OpenAI for GPT-4o and Whisper
- Twilio for telephony infrastructure
- The elderly community who inspired this project

---

## 📞 Support

- **Documentation:** docs/
- **Issues:** GitHub Issues
- **Email:** support@sahayak.ai

---

Built with ❤️ for our elders

> "Technology should adapt to humans, not the other way around."
