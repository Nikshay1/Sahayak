# Sahayak
**Overview**

Sahayak is a small FastAPI-based prototype that demonstrates a voice-driven assistant for basic medicine ordering and wallet debits. It parses a short spoken/text utterance, extracts an intent (MVP intent: ordering medicine), attempts an order, debits a local SQLite wallet, and replies via a simple TTS shim.

**Key Features**

- **Order Medicine:** Detects medicine ordering intents and places a fixed-price order.
- **Wallet Integration:** Debits a local SQLite wallet and records transactions in a ledger.
- **Text-to-Speech (TTS) Shim:** Prints assistant responses to stdout (placeholder for real TTS).

**Project Structure**

- [app/main.py](app/main.py): FastAPI app and `/speak` endpoint.
- [app/orchestrator.py](app/orchestrator.py): High-level flow: intent parsing, ordering, charging, and TTS.
- [app/intent.py](app/intent.py): Simple intent parser (MVP heuristics).
- [app/pharmacy.py](app/pharmacy.py): Mock pharmacy order placement.
- [app/wallet.py](app/wallet.py): SQLite-backed wallet and ledger logic.
- [app/tts.py](app/tts.py): TTS shim that prints outgoing speech.
- [app/models.py](app/models.py): Pydantic models used across the app.
- [scripts/init_db.py](scripts/init_db.py): Creates `data/sahayak.db` and seed user data.

**Requirements**

Install project dependencies from `requirements.txt` (tested on Python 3.10+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Initialize the database**

Run the DB initializer to create the SQLite DB and seed a demo user:

```bash
python scripts/init_db.py
```

This creates `data/sahayak.db` with a user (id=1, name='Sunita', balance=1000).

**Run the API**

Start the FastAPI app with `uvicorn`:

```bash
uvicorn app.main:app 
```

The app exposes one primary endpoint:

- `POST /speak` — Accepts JSON payload `{ "text": "..." }`. The server parses the text, handles intent, and prints TTS output to stdout.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/speak \
	-H "Content-Type: application/json" \
	-d '{"text":"My calcium medicines are finished"}'
```

**Notes & Next Steps**

- This repo is an MVP and uses simple heuristics in `app/intent.py` and fixed pricing in `app/pharmacy.py`.
- `app/tts.py` is a placeholder that prints messages; integrate a real TTS (e.g., gTTS, pyttsx3, or cloud TTS) for production.
- Add authentication, robust NLP (Rasa/Spacy/transformers), and error handling for a production-ready assistant.

If you'd like, I can:
- add OpenAPI examples for the `/speak` endpoint,
- replace TTS with a real audio response, or
- containerize the app with Docker.
