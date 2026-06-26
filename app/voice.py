"""
voice.py — Tamil voice reply generator (Phase 4 — OGG/Vorbis output)

Public interface:
    generate_voice_reply(advice_text, disease_name, is_healthy) -> str
    Returns the saved .ogg file path.

WhatsApp requires OGG/Vorbis format for voice notes.
Pipeline: Tamil text → gTTS (MP3 temp) → pydub (OGG/libvorbis) → delete MP3.

Requires ffmpeg on PATH for pydub audio conversion.
Windows install: winget install ffmpeg
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import subprocess

from gtts import gTTS

# ---------------------------------------------------------------------------
# ffmpeg path — needed for MP3 → OGG conversion
# winget installs to WinGet\Links which may not be on the system PATH
# ---------------------------------------------------------------------------
_WINGET_FFMPEG = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
)

def _ffmpeg_bin() -> str:
    """Return the path to ffmpeg, preferring the WinGet installation."""
    if _WINGET_FFMPEG.exists():
        return str(_WINGET_FFMPEG)
    return "ffmpeg"  # fall back to whatever is on PATH


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
AUDIO_DIR = Path("audio_replies")


# ---------------------------------------------------------------------------
# Translation dictionaries
# ---------------------------------------------------------------------------

DISEASE_TRANSLATIONS: dict[str, str] = {
    "Cercospora":     "செர்கோஸ்போரா இலை புள்ளி",
    "Early Blight":   "ஆரம்ப கருகல்",
    "Late Blight":    "கடும் கருகல்",
    "Powdery Mildew": "பொடி பூஞ்சை",
    "Leaf Spot":      "இலை புள்ளி",
    "Rust":           "துரு நோய்",
    "Mosaic Virus":   "மொசைக் வைரஸ்",
    "Healthy":        "ஆரோக்கியமான",
}

_DEFAULT_DISEASE_TAMIL = "பயிர் நோய்"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_disease_tamil(disease_name: Optional[str]) -> str:
    """
    Return Tamil translation for a disease name.
    Case-insensitive substring match so partial names still work.
    """
    if not disease_name:
        return _DEFAULT_DISEASE_TAMIL
    disease_lower = disease_name.lower()
    for eng, tamil in DISEASE_TRANSLATIONS.items():
        if eng.lower() in disease_lower:
            return tamil
    return _DEFAULT_DISEASE_TAMIL


def _build_tamil_summary(disease_name: Optional[str], is_healthy: bool = False) -> str:
    """Build the Tamil voice script string."""
    if is_healthy or (disease_name and disease_name.lower() == "healthy"):
        return (
            "நண்பரே, உங்கள் பயிர் ஆரோக்கியமாக உள்ளது. "
            "தொடர்ந்து பராமரிக்கவும். "
            "கிசான் உதவி எண்: 1800-180-1551"
        )

    disease_tamil = _get_disease_tamil(disease_name)
    treatment_tamil = "பூஞ்சை கொல்லி மருந்து"

    return (
        f"நண்பரே, உங்கள் பயிரில் {disease_tamil} நோய் கண்டறியப்பட்டது. "
        f"உடனே {treatment_tamil} தெளிக்கவும். "
        "கிசான் உதவி எண்: 1800-180-1551"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_voice_reply(
    advice_text: str,
    disease_name: Optional[str] = None,
    is_healthy: bool = False,
) -> str:
    """
    Generate a Tamil OGG voice note from the crop advisory.

    Pipeline:
      1. Build Tamil summary from disease name
      2. gTTS → temporary MP3  (gTTS only exports MP3)
      3. pydub → convert MP3 to OGG/libvorbis  (WhatsApp format)
      4. Delete temporary MP3
      5. Return OGG file path

    Args:
        advice_text:  Full English advice string (used for logging context).
        disease_name: Disease name from Plant.id — used for Tamil translation.
        is_healthy:   True if Plant.id found the crop healthy.

    Returns:
        Absolute path string to the saved .ogg file.

    Raises:
        RuntimeError: If ffmpeg is not installed (pydub dependency).
        Exception:    Propagated from gTTS on network failures.
    """
    # Ensure output directory exists
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Build Tamil script
    tamil_text = _build_tamil_summary(disease_name, is_healthy=is_healthy)

    # Auto-generate filenames with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mp3_path = str(AUDIO_DIR / f"reply_{timestamp}.mp3")   # temp
    ogg_path = str(AUDIO_DIR / f"reply_{timestamp}.ogg")   # final

    logger.info("🎙️  Generating Tamil voice reply → %s", ogg_path)
    logger.debug("Tamil script: %s", tamil_text)

    # Step 1 — gTTS → MP3
    tts = gTTS(text=tamil_text, lang="ta", slow=False)
    tts.save(mp3_path)
    logger.info("🎵 MP3 saved (%d bytes) — converting to OGG …", Path(mp3_path).stat().st_size)

    # Step 2 — ffmpeg: MP3 → OGG/libvorbis (WhatsApp voice note format)
    # Using subprocess directly — avoids pydub's audioop dependency
    # which was removed in Python 3.13+
    subprocess.run(
        [
            _ffmpeg_bin(),
            "-y",                   # overwrite output without asking
            "-i", mp3_path,         # input MP3
            "-c:a", "libvorbis",    # OGG/Vorbis codec
            "-q:a", "4",            # quality level 4 (~128 kbps)
            ogg_path,               # output OGG
        ],
        check=True,
        capture_output=True,        # suppress ffmpeg console output
    )
    logger.info("✅ OGG saved — %d bytes", Path(ogg_path).stat().st_size)

    # Step 3 — delete temporary MP3
    os.remove(mp3_path)
    logger.debug("🗑️  Temp MP3 deleted: %s", mp3_path)

    # Terminal preview (encode safely for Windows cp1252 console)
    def _safe(s: str) -> str:
        return s.encode("utf-8", errors="replace").decode("utf-8")

    print("\n" + "─" * 50)
    print("🎙️  Tamil voice script:")
    print(f"   {_safe(tamil_text)}")
    print(f"   Saved → {ogg_path}")
    print("─" * 50 + "\n")

    return ogg_path
