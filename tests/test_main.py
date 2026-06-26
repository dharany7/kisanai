"""
tests/test_main.py — Smoke + webhook tests for KisanAI (Phase 3)

Run with:  pytest tests/ -v
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_root_returns_200_and_correct_body():
    """GET / should return HTTP 200 with the expected status and version."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "KisanAI is live"
    assert data["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# POST /webhook — TEXT message
# ---------------------------------------------------------------------------

def test_webhook_text_message_returns_twiml():
    """A plain text WhatsApp message should get a TwiML text reply."""
    response = client.post(
        "/webhook",
        data={
            "From": "whatsapp:+919876543210",
            "Body": "My tomato leaves are turning yellow",
            "NumMedia": "0",
        },
    )
    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]
    body = response.text
    assert '<?xml version="1.0"' in body
    assert "<Response>" in body
    assert "<Message>" in body
    assert "Vanakkam" in body
    assert "GOOD PHOTO TIPS" in body      # New reply format — photo guidance tips


# ---------------------------------------------------------------------------
# POST /webhook — IMAGE message (mocked pipeline)
# ---------------------------------------------------------------------------

def test_webhook_image_message_returns_twiml():
    """
    A WhatsApp message with an image should call the Vision+Gemini pipeline
    and return TwiML with the AI advice.

    We mock analyze_crop and get_farming_advice so no real API calls are made.
    """
    fake_disease = {
        "is_healthy": False,
        "disease": "Early Blight",
        "probability": 87.5,
        "raw_suggestion": "Fungal disease on tomato.",
    }
    fake_advice = (
        "🌱 PROBLEM: Early Blight — a fungal disease.\n"
        "💊 TREATMENT: Spray Mancozeb 2.5g/litre.\n"
        "🛡️ PREVENTION: Avoid overhead watering. Rotate crops.\n"
        "📞 HELPLINE: Kisan Call Centre: 1800-180-1551\n"
        "உங்கள் பயிர் சீக்கிரம் குணமாகும்! 🌾"
    )

    import os

    fake_env = {
        "TWILIO_ACCOUNT_SID": "ACfake",
        "TWILIO_AUTH_TOKEN": "faketoken",
        "PLANT_ID_API_KEY": "fakekey",
        "GEMINI_API_KEY": "fakegemini",
    }

    with (
        patch.dict(os.environ, fake_env),
        patch("app.webhook.analyze_crop", new_callable=AsyncMock, return_value=fake_disease),
        patch("app.webhook.get_farming_advice", new_callable=AsyncMock, return_value=fake_advice),
    ):
        response = client.post(
            "/webhook",
            data={
                "From": "whatsapp:+919876543210",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/fake/media/image.jpg",
                "MediaContentType0": "image/jpeg",
            },
        )

    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]
    body = response.text
    assert "<Response>" in body
    assert "Early Blight" in body or "TREATMENT" in body


# ---------------------------------------------------------------------------
# POST /webhook — empty / unknown message
# ---------------------------------------------------------------------------

def test_webhook_empty_message_returns_fallback():
    """An empty message body with no media should return the fallback TwiML reply."""
    response = client.post(
        "/webhook",
        data={
            "From": "whatsapp:+919876543210",
            "Body": "",
            "NumMedia": "0",
        },
    )
    assert response.status_code == 200
    assert "<Response>" in response.text
    assert "Vanakkam" in response.text


# ---------------------------------------------------------------------------
# Unit: build_twiml escapes XML special characters
# ---------------------------------------------------------------------------

def test_build_twiml_escapes_xml():
    """build_twiml must escape &, <, > so the XML remains valid."""
    from app.webhook import build_twiml

    twiml = build_twiml("Spray <Mancozeb> & water")
    assert "&lt;Mancozeb&gt;" in twiml
    assert "&amp;" in twiml
    assert "<Response>" in twiml
