"""
KisanAI — FastAPI Entry Point  (Phase 5 — RAG)
Run with: uvicorn app.main:app --reload
"""

import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Windows UTF-8 fix — emoji in print() causes UnicodeEncodeError on CP1252
# Reconfigure stdout/stderr to UTF-8 before any other import writes to them.
# ---------------------------------------------------------------------------
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from app.webhook import handle_whatsapp_message

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="KisanAI",
    description="WhatsApp-based AI crop advisory system for Indian smallholder farmers",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Startup: pre-load RAG knowledge base into ChromaDB
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialise ChromaDB knowledge base when the server boots."""
    from app.rag import initialize_knowledge_base
    initialize_knowledge_base()
    print("KisanAI knowledge base ready")

# ---------------------------------------------------------------------------
# CORS — allow all origins during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Audio directory (created by voice.py on first use)
# ---------------------------------------------------------------------------
AUDIO_DIR = Path("audio_replies")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health-check / welcome endpoint."""
    return {"status": "KisanAI is live", "version": "1.0.0"}


@app.post("/webhook", response_class=PlainTextResponse)
async def webhook(request: Request):
    """
    Twilio WhatsApp webhook endpoint.

    Twilio POSTs application/x-www-form-urlencoded data.
    We delegate all parsing and response-building to handle_whatsapp_message(),
    which reads FastAPI Form fields and returns a TwiML PlainTextResponse.
    """
    # Log raw bytes for debugging
    raw_body = await request.body()
    logger.debug("Raw webhook body (%d bytes): %s", len(raw_body), raw_body.decode())

    # Parse form data and dispatch to webhook handler
    form_data = await request.form()
    form_dict = dict(form_data)

    return await handle_whatsapp_message(
        From=form_dict.get("From"),
        Body=form_dict.get("Body"),
        MediaUrl0=form_dict.get("MediaUrl0"),
        MediaContentType0=form_dict.get("MediaContentType0"),
        NumMedia=form_dict.get("NumMedia", "0"),
    )


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """
    Serve a generated Tamil voice note MP3 file.

    Twilio fetches this URL when sending a WhatsApp voice message.
    The filename is the auto-generated timestamped name from voice.py.

    Security: os.path.basename() strips any path components to prevent
    directory traversal attacks (e.g. ../../etc/passwd).

    Returns:
        audio/mpeg FileResponse on success.
        HTTP 404 if the file does not exist.
    """
    # Strip any path components — only the bare filename is allowed
    safe_name = os.path.basename(filename)
    file_path = AUDIO_DIR / safe_name

    if not file_path.exists():
        logger.warning("Audio file not found: %s", file_path)
        raise HTTPException(status_code=404, detail=f"Audio file '{safe_name}' not found")

    logger.info("🔊 Serving audio file: %s (%d bytes)", safe_name, file_path.stat().st_size)
    return FileResponse(
        path=str(file_path),
        media_type="audio/ogg",
        filename=safe_name,
    )
