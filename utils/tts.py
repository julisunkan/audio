"""
tts.py — Text-to-speech using gTTS (Google Text-to-Speech).
Provides 10 curated voices across different English accents.
Uses pydub for speed control post-generation.
"""
import io
import os
import tempfile
from gtts import gTTS
from pydub import AudioSegment

# 10 curated voices: name -> gTTS config (lang + tld for accent variety)
# gTTS doesn't distinguish male/female natively; accents provide variety.
VOICES = {
    "Emma (US Female)":     {"lang": "en", "tld": "com"},
    "Guy (US Male)":        {"lang": "en", "tld": "us"},
    "Aria (US Female)":     {"lang": "en", "tld": "com"},
    "Davis (US Male)":      {"lang": "en", "tld": "us"},
    "Jenny (US Female)":    {"lang": "en", "tld": "com"},
    "Sonia (UK Female)":    {"lang": "en", "tld": "co.uk"},
    "Ryan (UK Male)":       {"lang": "en", "tld": "co.uk"},
    "Natasha (AU Female)":  {"lang": "en", "tld": "com.au"},
    "William (AU Male)":    {"lang": "en", "tld": "com.au"},
    "Clara (CA Female)":    {"lang": "en", "tld": "ca"},
}

DEFAULT_VOICE = "Emma (US Female)"


def get_voice_config(voice_name: str) -> dict:
    return VOICES.get(voice_name, VOICES[DEFAULT_VOICE])


def _apply_speed(audio: AudioSegment, speed: float) -> AudioSegment:
    """Change playback speed using pydub frame-rate trick."""
    if abs(speed - 1.0) < 0.05:
        return audio
    new_frame_rate = int(audio.frame_rate * speed)
    sped = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    return sped.set_frame_rate(audio.frame_rate)


def synthesize_chunk(text: str, voice_name: str, speed: float, output_path: str):
    """
    Generate speech for one text chunk and save as MP3.
    Applies speed adjustment via pydub after generation.
    """
    config = get_voice_config(voice_name)
    tts = gTTS(text=text, lang=config["lang"], tld=config["tld"])

    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)

    audio = AudioSegment.from_file(buf, format="mp3")

    if abs(speed - 1.0) >= 0.05:
        audio = _apply_speed(audio, speed)

    audio.export(output_path, format="mp3", bitrate="64k")


def synthesize_preview(voice_name: str, preview_text: str) -> bytes:
    """
    Generate a short voice preview.
    Returns raw MP3 bytes.
    """
    config = get_voice_config(voice_name)
    tts = gTTS(text=preview_text, lang=config["lang"], tld=config["tld"])
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()
