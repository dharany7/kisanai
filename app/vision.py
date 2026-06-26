"""
vision.py — Crop disease detection via Plant.id API (Phase 3)

Public interface:
    analyze_crop(image_url, twilio_sid, twilio_token) -> dict
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PLANT_ID_URL = "https://plant.id/api/v3/health_assessment"


async def _download_image(
    url: str,
    twilio_sid: str,
    twilio_token: str,
) -> bytes:
    """
    Download a Twilio media URL with HTTP Basic Auth.
    Twilio requires (Account SID, Auth Token) as username/password.
    """
    logger.info("⬇️  Downloading image from Twilio …")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, auth=(twilio_sid, twilio_token), follow_redirects=True)
        response.raise_for_status()
    logger.info("✅ Image downloaded — %d bytes", len(response.content))
    return response.content


def _to_base64(image_bytes: bytes) -> str:
    """Encode raw image bytes as a base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


async def _call_plant_id(base64_image: str, api_key: str) -> dict:
    """
    POST the base64-encoded image to the Plant.id health assessment endpoint
    and return the raw JSON response dict.
    """
    payload = {
        "images": [f"data:image/jpeg;base64,{base64_image}"],
        "health": "all",
    }
    headers = {
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }
    logger.info("🔬 Sending image to Plant.id for analysis …")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(PLANT_ID_URL, json=payload, headers=headers)
        response.raise_for_status()
    return response.json()


def _parse_plant_id_response(data: dict) -> dict:
    """
    Extract the fields we care about from the Plant.id JSON response.

    Plant.id v3 health_assessment response shape (simplified):
    {
      "result": {
        "is_healthy": { "binary": true/false, "probability": 0.95 },
        "disease": {
          "suggestions": [
            {
              "id": "...",
              "name": "Early blight",
              "probability": 0.87,
              "details": { "description": "...", "treatment": { ... } }
            }
          ]
        }
      }
    }
    """
    result = data.get("result", {})

    # is_healthy
    health_info = result.get("is_healthy", {})
    is_healthy: bool = health_info.get("binary", True)

    disease_name: Optional[str] = None
    probability: float = 0.0
    raw_suggestion: str = ""

    if not is_healthy:
        suggestions = result.get("disease", {}).get("suggestions", [])
        if suggestions:
            top = suggestions[0]
            disease_name = top.get("name", "Unknown disease")
            probability = round(top.get("probability", 0.0) * 100, 1)

            # Try to get a brief description for context
            details = top.get("details") or {}
            raw_suggestion = (
                details.get("description")
                or details.get("cause")
                or disease_name
            )
            # Truncate to avoid sending walls of text to Gemini
            if len(raw_suggestion) > 300:
                raw_suggestion = raw_suggestion[:300] + "…"

    return {
        "is_healthy": is_healthy,
        "disease": disease_name,
        "probability": probability,
        "raw_suggestion": raw_suggestion,
    }


async def analyze_crop(
    image_url: str,
    twilio_sid: str,
    twilio_token: str,
) -> dict:
    """
    Full pipeline: download image → base64 → Plant.id → parsed result dict.

    Args:
        image_url:    Twilio MediaUrl0 value from the incoming webhook.
        twilio_sid:   TWILIO_ACCOUNT_SID for Basic Auth on the media URL.
        twilio_token: TWILIO_AUTH_TOKEN for Basic Auth on the media URL.

    Returns:
        {
            "is_healthy": bool,
            "disease":    str | None,
            "probability": float,        # 0–100
            "raw_suggestion": str,
        }

    Raises:
        httpx.HTTPStatusError: if the download or Plant.id request fails.
        KeyError / ValueError:  if the Plant.id response is malformed.
    """
    api_key = os.getenv("PLANT_ID_API_KEY", "")
    if not api_key:
        raise EnvironmentError("PLANT_ID_API_KEY is not set in .env")

    image_bytes = await _download_image(image_url, twilio_sid, twilio_token)
    base64_image = _to_base64(image_bytes)
    raw_response = await _call_plant_id(base64_image, api_key)

    result = _parse_plant_id_response(raw_response)

    # Terminal summary
    print("\n" + "─" * 50)
    print(f"🌿 Plant.id result:")
    print(f"   Healthy     : {result['is_healthy']}")
    if not result["is_healthy"]:
        print(f"   Disease     : {result['disease']}")
        print(f"   Probability : {result['probability']}%")
    print("─" * 50 + "\n")

    return result
