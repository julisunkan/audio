"""
audio.py — Merge audio chunks and compress to MP3 at 64kbps.
Uses pydub for audio processing.
"""
import os
from pydub import AudioSegment


def merge_chunks(chunk_paths: list[str], output_path: str, bitrate: str = "64k"):
    """
    Merge a list of MP3 chunk files into a single MP3 file.
    Compresses at the given bitrate (default 64kbps).
    Deletes chunk files after merging.
    """
    if not chunk_paths:
        raise ValueError("No audio chunks to merge")

    combined = AudioSegment.empty()
    for path in chunk_paths:
        segment = AudioSegment.from_file(path, format="mp3")
        combined += segment

    # Export as compressed MP3
    combined.export(output_path, format="mp3", bitrate=bitrate)

    # Clean up chunk files
    for path in chunk_paths:
        try:
            os.remove(path)
        except OSError:
            pass


def add_background_music(speech_path: str, music_path: str, output_path: str,
                          music_volume_db: float = -20.0):
    """
    Overlay background music on speech audio.
    Music is looped to match speech duration and reduced in volume.
    """
    speech = AudioSegment.from_file(speech_path, format="mp3")
    music = AudioSegment.from_file(music_path)

    # Loop music to fill speech duration
    loops = (len(speech) // len(music)) + 2
    looped_music = music * loops
    looped_music = looped_music[: len(speech)]

    # Lower music volume
    looped_music = looped_music + music_volume_db

    # Overlay
    result = speech.overlay(looped_music)
    result.export(output_path, format="mp3", bitrate="64k")
