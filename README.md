# KisanAI 🌾

> **WhatsApp-based AI crop advisory system for Indian smallholder farmers.**  
> Farmers send a photo of their diseased crop + a voice/text message in Tamil or Hindi → KisanAI diagnoses the disease and replies with treatment advice.

---

## Table of Contents

1. [Project Structure](#project-structure)  
2. [Prerequisites](#prerequisites)  
3. [Setup — Step by Step](#setup--step-by-step)  
4. [Environment Variables](#environment-variables)  
5. [Running the Server](#running-the-server)  
6. [Running Tests](#running-tests)  
7. [API Reference](#api-reference)  
8. [Architecture Overview](#architecture-overview)  
9. [Roadmap](#roadmap)  

---

## Project Structure

```
kisanai/
├── app/
│   ├── __init__.py     # Package marker
│   ├── main.py         # FastAPI entry point (GET /, POST /webhook)
│   ├── webhook.py      # WhatsApp message parser & Twilio reply sender
│   ├── vision.py       # Crop disease detection via Plant.id API
│   ├── rag.py          # ChromaDB knowledge-base retrieval
│   ├── voice.py        # gTTS text-to-speech (Hindi & Tamil)
│   └── agent.py        # Pipeline orchestrator (Vision → RAG → LLM → TTS)
├── knowledge_base/
│   └── sample_disease.txt   # Sample crop disease entries
├── tests/
│   └── test_main.py    # Smoke tests
├── .env.example        # Environment variable template
├── requirements.txt    # Pinned Python dependencies
└── README.md           # This file
```

---

## Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Python | 3.10+ | `python --version` |
| pip | 23+ | `pip --version` |
| git | any | `git --version` |

> **Windows users:** Use **PowerShell** or **Command Prompt**. All commands below work on Windows, macOS, and Linux unless noted.

---

## Setup — Step by Step

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/kisanai.git
cd kisanai
```

### 2 — Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

> You should see `(venv)` appear at the start of your terminal prompt.

### 3 — Install all dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ `sentence-transformers` and `chromadb` are large packages — the first install may take 2–5 minutes.

### 4 — Set up environment variables

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in any text editor and replace every `your_..._here` placeholder with your real credentials. See [Environment Variables](#environment-variables) below for details.

---

## Environment Variables

| Variable | Description | Where to get it |
|----------|-------------|-----------------|
| `TWILIO_ACCOUNT_SID` | Twilio account identifier | [Twilio Console](https://console.twilio.com) → Account Info |
| `TWILIO_AUTH_TOKEN` | Twilio authentication secret | Same page as above |
| `PLANT_ID_API_KEY` | Plant.id crop disease API key | [plant.id](https://web.plant.id/) → API Keys |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | [Anthropic Console](https://console.anthropic.com) → API Keys |

> **Never commit your `.env` file to version control.** It is already listed in `.gitignore`.

---

## Running the Server

```bash
uvicorn app.main:app --reload
```

Expected terminal output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### What you will see in the browser

Open **http://localhost:8000** — you should see:

```json
{
  "status": "KisanAI is live",
  "version": "1.0.0"
}
```

Open **http://localhost:8000/docs** — interactive Swagger UI where you can test every endpoint in the browser.

Open **http://localhost:8000/redoc** — alternative ReDoc API documentation.

---

## Running Tests

```bash
# From the kisanai/ directory (with venv active)
pytest tests/ -v
```

Expected output:

```
tests/test_main.py::test_root_returns_200_and_correct_body PASSED
tests/test_main.py::test_webhook_returns_received         PASSED
```

---

## API Reference

### `GET /`

Health check endpoint.

**Response:**
```json
{
  "status": "KisanAI is live",
  "version": "1.0.0"
}
```

---

### `POST /webhook`

Receives incoming WhatsApp messages forwarded by Twilio.

**Request body:** `application/x-www-form-urlencoded` (standard Twilio format)

**Response:**
```json
{
  "status": "received",
  "message": "processing"
}
```

The raw request body is also printed to the server terminal for debugging.

---

## Architecture Overview

```
Farmer (WhatsApp)
       │
       ▼
  Twilio API  ──POST──▶  /webhook  (main.py)
                               │
                               ▼
                        webhook.py  — parse message + media URL
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
              vision.py            (text query only)
            (Plant.id API)               │
                    │                    │
                    └──────────┬─────────┘
                               ▼
                            rag.py  — ChromaDB retrieval
                               │
                               ▼
                           agent.py  — Anthropic Claude synthesis
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
              voice.py              Text reply
            (gTTS MP3)                   │
                    └──────────┬─────────┘
                               ▼
                       Twilio API  ──▶  Farmer (WhatsApp)
```

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Project scaffolding | ✅ Done |
| 2 | Twilio webhook parsing + reply | 🔜 Next |
| 3 | Plant.id vision integration | 🔜 Planned |
| 4 | ChromaDB RAG knowledge base | 🔜 Planned |
| 5 | gTTS voice replies (Hindi/Tamil) | 🔜 Planned |
| 6 | Claude LLM orchestration | 🔜 Planned |
| 7 | Ngrok / production deployment | 🔜 Planned |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)
