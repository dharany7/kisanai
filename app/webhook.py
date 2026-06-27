"""
webhook.py — WhatsApp message handler (Phase 4)

Routes:
  TEXT  → photo tips message
  IMAGE → analyze_crop → get_farming_advice → TwiML text reply
          + generate_voice_reply → Twilio media message (Tamil audio)
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.rest import Client as TwilioClient
router = APIRouter()

from app.agent import get_farming_advice
from app.vision import analyze_crop
from app.voice import generate_voice_reply

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message type
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# TwiML builder
# ---------------------------------------------------------------------------

def build_twiml(reply_text: str) -> str:
    """Wrap reply text in a TwiML <Response><Message> envelope."""
    safe = (
        reply_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        f"  <Message>{safe}</Message>\n"
        "</Response>"
    )


# ---------------------------------------------------------------------------
# Core handler
# ---------------------------------------------------------------------------

async def handle_whatsapp_message(
    From: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    NumMedia: Optional[str] = Form(None),
) -> PlainTextResponse:
    """
    Main webhook handler.

    TEXT    → photo tips message
    IMAGE   → Vision → Gemini pipeline → text reply + Tamil voice note
    UNKNOWN → fallback greeting
    """

    sender: str = From or "unknown"
    body: str = (Body or "").strip()
    num_media: int = int(NumMedia or "0")
    has_image: bool = num_media > 0 and bool(MediaUrl0)

    # ── Classify ──────────────────────────────────────────────────────────────
    if has_image:
        msg_type = MessageType.IMAGE
    elif body:
        msg_type = MessageType.TEXT
    else:
        msg_type = MessageType.UNKNOWN

    # ── Terminal log ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"📱 Sender      : {sender}")
    print(f"📌 Type        : {msg_type.value}")
    if msg_type == MessageType.TEXT:
        print(f"💬 Body        : {body}")
    elif msg_type == MessageType.IMAGE:
        print(f"🖼️  Image URL   : {MediaUrl0}")
        print(f"📎 Content-Type: {MediaContentType0 or 'unknown'}")
        if body:
            print(f"💬 Caption     : {body}")
    print("=" * 60 + "\n")

    # ── Route ─────────────────────────────────────────────────────────────────
    if msg_type == MessageType.IMAGE:
        reply = await _handle_image(MediaUrl0, sender)

    elif msg_type == MessageType.TEXT:
        reply = (
            "Vanakkam! 🌾 I am KisanAI — your crop disease advisor.\n\n"
            "To get accurate diagnosis, please send a photo following these tips:\n"
            "📸 GOOD PHOTO TIPS:\n"
            "- Take photo in daylight (not dark)\n"
            "- Go close to the diseased leaf or stem\n"
            "- Make sure the affected part fills the photo\n"
            "- Use your phone camera directly — do not send screenshots\n\n"
            "Send your crop photo now and I will diagnose it!\n"
            "உங்கள் பயிரை காப்பாற்றுவோம்! 🌿"
        )

    else:  # UNKNOWN (empty body, no media)
        reply = (
            "Vanakkam! 🙏 I am KisanAI — your crop doctor.\n\n"
            "📸 Send me a photo of your crop and I will tell you "
            "what disease it has and how to treat it.\n\n"
            "📞 Kisan Call Centre: 1800-180-1551"
        )

    return PlainTextResponse(content=build_twiml(reply), media_type="text/xml")


# ---------------------------------------------------------------------------
# Image pipeline
# ---------------------------------------------------------------------------

async def _handle_image(image_url: str, sender: str) -> str:
    """
    Full pipeline for an incoming crop photo:
      1. Download & analyze image (Plant.id)
      2. Generate farming advice (Gemini)
      3. Generate Tamil voice note (gTTS)  ← Phase 4
      4. Send voice note via Twilio media message ← Phase 4
      5. Return text advice (caller wraps in TwiML)

    Voice sending is best-effort — a failure never breaks the text reply.
    """
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")

    if not twilio_sid or not twilio_token:
        logger.error("Twilio credentials missing from .env")
        return (
            "⚠️ Server configuration error. "
            "Please contact support.\n"
            "📞 Kisan Call Centre: 1800-180-1551"
        )

    try:
        logger.info("🌾 Starting crop analysis pipeline …")

        # Step 1 — Vision (Plant.id)
        disease_result = await analyze_crop(image_url, twilio_sid, twilio_token)

        # Step 2 — Text advice (Gemini)
        advice = await get_farming_advice(disease_result)

        # Step 3 & 4 — Tamil voice note (best-effort, runs after text is ready)
        asyncio.ensure_future(
            _send_voice_note(
                sender=sender,
                advice_text=advice,
                disease_name=disease_result.get("disease"),
                is_healthy=disease_result.get("is_healthy", False),
                twilio_sid=twilio_sid,
                twilio_token=twilio_token,
            )
        )

        return advice

    except Exception as exc:
        logger.error("❌ Pipeline error: %s", exc, exc_info=True)
        return (
            "⚠️ Sorry, I could not analyse your crop photo right now.\n\n"
            "Please try:\n"
            "• Sending a clearer, well-lit photo\n"
            "• Making sure the diseased part is visible\n\n"
            "📞 Kisan Call Centre: 1800-180-1551\n"
            "மன்னிக்கவும் — மீண்டும் முயற்சி செய்யுங்கள்! 🙏"
        )


async def _send_voice_note(
    sender: str,
    advice_text: str,
    disease_name: Optional[str],
    is_healthy: bool,
    twilio_sid: str,
    twilio_token: str,
) -> None:
    """
    Generate Tamil audio and send it as a WhatsApp voice note via Twilio.

    This runs asynchronously (fire-and-forget via ensure_future) so it
    never delays the main text TwiML reply to the farmer.

    Requires NGROK_BASE_URL and TWILIO_WHATSAPP_NUMBER in .env.
    """
    ngrok_base = os.getenv("NGROK_BASE_URL", "").rstrip("/")
    whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    if not ngrok_base:
        logger.warning("⚠️  NGROK_BASE_URL not set — skipping voice note")
        return
    if not whatsapp_from:
        logger.warning("⚠️  TWILIO_WHATSAPP_NUMBER not set — skipping voice note")
        return

    try:
        # Generate audio in a thread (gTTS is blocking I/O)
        audio_path = await asyncio.to_thread(
            generate_voice_reply,
            advice_text,
            disease_name,
            is_healthy,
        )

        # Build public URL Twilio can fetch
        filename = Path(audio_path).name
        audio_public_url = f"{ngrok_base}/audio/{filename}"
        logger.info("🔊 Audio public URL: %s", audio_public_url)

        # Send via Twilio REST API (blocking, run in thread)
        def _send():
            client = TwilioClient(twilio_sid, twilio_token)
            msg = client.messages.create(
                from_=whatsapp_from,
                to=sender,
                media_url=[audio_public_url],
                body="🎙️ குரல் பதில் / Voice Reply",
            )
            return msg.sid

        msg_sid = await asyncio.to_thread(_send)
        logger.info("✅ Voice note sent — SID: %s", msg_sid)
        print(f"\n🔊 Voice note dispatched to {sender} (SID: {msg_sid})\n")

    except Exception as exc:
        # Log but never raise — voice failure must not affect text reply
        logger.error("❌ Voice note failed: %s", exc, exc_info=True)
        print(f"\n⚠️  Voice note skipped: {exc}\n")
