"""
tts.py — Text-to-speech using Microsoft Edge TTS (edge-tts).
Provides 10 curated voices across different genders and accents.
Runs async TTS in a thread-safe manner.
"""
import asyncio
import os
import tempfile
import edge_tts

# 10 curated voices: name -> edge-tts voice ID
VOICES = {
    "Emma (US Female)":     "en-US-EmmaNeural",
    "Guy (US Male)":        "en-US-GuyNeural",
    "Aria (US Female)":     "en-US-AriaNeural",
    "Davis (US Male)":      "en-US-DavisNeural",
    "Jenny (US Female)":    "en-US-JennyNeural",
    "Sonia (UK Female)":    "en-GB-SoniaNeural",
    "Ryan (UK Male)":       "en-GB-RyanNeural",
    "Natasha (AU Female)":  "en-AU-NatashaNeural",
    "William (AU Male)":    "en-AU-WilliamNeural",
    "Clara (CA Female)":    "en-CA-ClaraNeural",
}

DEFAULT_VOICE = "Emma (US Female)"


def get_voice_id(voice_name: str) -> str:
    return VOICES.get(voice_name, VOICES[DEFAULT_VOICE])


def apply_speed_tag(rate: float) -> str:
    """Convert numeric speed (0.75–1.5) to SSML rate string."""
    if rate < 0.85:
        return "-20%"
    elif rate < 0.95:
        return "-10%"
    elif rate < 1.05:
        return "+0%"
    elif rate < 1.2:
        return "+15%"
    else:
        return "+30%"


async def _synthesize_chunk(text: str, voice_id: str, rate_str: str, output_path: str):
    """Async function: generate speech for one chunk and save as MP3."""
    communicate = edge_tts.Communicate(text, voice_id, rate=rate_str)
    await communicate.save(output_path)


def synthesize_chunk(text: str, voice_name: str, speed: float, output_path: str):
    """
    Synchronous wrapper around the async edge-tts call.
    Runs in its own event loop (safe to call from threads).
    """
    voice_id = get_voice_id(voice_name)
    rate_str = apply_speed_tag(speed)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _synthesize_chunk(text, voice_id, rate_str, output_path)
        )
    finally:
        loop.close()


def synthesize_preview(voice_name: str, preview_text: str) -> bytes:
    """
    Generate a short audio preview for a voice.
    Returns raw audio bytes (MP3).
    """
    voice_id = get_voice_id(voice_name)

    async def _run():
        chunks = []
        communicate = edge_tts.Communicate(preview_text, voice_id)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
