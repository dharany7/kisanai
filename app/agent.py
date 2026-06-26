"""
agent.py — AI advisory orchestrator via Google Gemini (Phase 3)

Public interface:
    get_farming_advice(disease_result: dict) -> str
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client — configured once at module load
# ---------------------------------------------------------------------------
_GEMINI_MODEL = "gemini-1.5-flash"

def _get_client() -> genai.Client:
    """Create a Gemini client from the API key in .env."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in .env")
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# Low-confidence threshold — Tamil warning shown when Plant.id < 60%
_LOW_CONFIDENCE_THRESHOLD = 60.0

_LOW_CONFIDENCE_PREFIX = (
    "📸 நம்பகத்தன்மை குறைவாக உள்ளது ({probability}%). "
    "தயவுசெய்து நோய்வாய்ப்பட்ட இலையை நெருக்கமாக தெளிவாக "
    "படம் எடுத்து அனுப்பவும்.\n\n"
)

_HEALTHY_REPLY = (
    "✅ Your crop looks healthy! Keep it up!\n\n"
    "உங்கள் பயிர் ஆரோக்கியமாக உள்ளது! 🌿\n\n"
    "📞 For any farming questions: Kisan Call Centre: 1800-180-1551"
)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

async def get_farming_advice(disease_result: dict) -> str:
    """
    Generate a farmer-friendly advisory using Google Gemini.

    Args:
        disease_result: Dict returned by vision.analyze_crop(), e.g.:
            {
                "is_healthy": False,
                "disease": "Early Blight",
                "probability": 87.5,
                "raw_suggestion": "Fungal disease caused by Alternaria solani …"
            }

    Returns:
        Formatted advisory string ready to send as a WhatsApp message.
    """
    # ── Healthy crop → canned reply, no LLM call needed ───────────────────
    if disease_result.get("is_healthy"):
        logger.info("🌿 Crop is healthy — returning canned reply")
        return _HEALTHY_REPLY

    disease_name = disease_result.get("disease") or "Unknown disease"
    probability = disease_result.get("probability", 0.0)

    # Build the exact prompt
    prompt = f"""You are KisanAI, an agricultural expert 
for Indian farmers. Give specific advice.

Disease found: {disease_name}
Confidence: {probability}%

Reply in this EXACT format, nothing else:

⚠️ DISEASE: {disease_name} (இலை நோய்)

💊 TREATMENT:
- Buy Mancozeb 75% WP or Copper Oxychloride from your local agri shop
- Mix 2.5 grams per 1 litre of water
- Spray on affected leaves every 7 days for 3 weeks
- Spray early morning or evening, not in hot sun

🛡️ PREVENTION:
- Remove and burn infected leaves immediately
- Do not water leaves from above, water only at roots
- Keep space between plants for air circulation

📞 Kisan Call Centre: 1800-180-1551

உங்கள் பயிர் விரைவில் குணமாகும்! தைரியமாக இருங்கள்! 🌿"""

    logger.info("🤖 Calling Gemini (%s) for farming advice …", _GEMINI_MODEL)

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        advice = response.text.strip()

        # Prepend Tamil low-confidence warning if needed
        if probability < _LOW_CONFIDENCE_THRESHOLD:
            prefix = _LOW_CONFIDENCE_PREFIX.format(probability=probability)
            advice = prefix + advice
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return (
            "⚠️ Disease detected on your crop.\n\n"
            "💊 TREATMENT:\n"
            "• Buy Mancozeb 75% WP from your local agri shop\n"
            "• Mix 2.5 grams per 1 litre of water\n"
            "• Spray every 7 days for 3 weeks\n\n"
            "🛡️ PREVENTION:\n"
            "• Remove infected leaves immediately\n"
            "• Water only at roots, not on leaves\n\n"
            "📞 Kisan Call Centre: 1800-180-1551\n"
            "உங்கள் பயிர் விரைவில் குணமாகும்! 🌿"
        )

    # Terminal log
    print("\n" + "─" * 50)
    print("🤖 Gemini advisory generated:")
    print(advice)
    print("─" * 50 + "\n")

    return advice
