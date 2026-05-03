"""
groq_utils.py — Use Groq AI to clean and format text before narration.
Skipped when text > 5000 chars to save resources.
"""
from db import get_setting

STYLE_PROMPTS = {
    "storytelling": (
        "You are a professional audiobook narrator editor. "
        "Clean the following text for narration: fix punctuation, remove headers, "
        "page numbers, and formatting artifacts. Keep the narrative flow natural. "
        "Return only the cleaned text, no explanations."
    ),
    "news": (
        "You are a news anchor script editor. "
        "Clean and format the following text for clear, professional news-style narration. "
        "Fix punctuation, remove formatting noise. Return only the cleaned text."
    ),
    "calm": (
        "You are a meditation and calm narration script editor. "
        "Clean the following text for peaceful, slow-paced narration. "
        "Smooth out harsh transitions, fix punctuation. Return only the cleaned text."
    ),
}

CHAR_LIMIT = 5000


def clean_text(text: str, style: str = "storytelling") -> str:
    """
    Use Groq to clean text. Returns original text if too long or API key missing.
    """
    if len(text) > CHAR_LIMIT:
        return text  # Skip AI cleaning for large texts

    api_key = get_setting("groq_api_key")
    if not api_key:
        return text  # No key configured

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["storytelling"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:CHAR_LIMIT]},
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Groq] Cleaning failed: {e}")
        return text  # Fall back to original


def generate_preview_text(voice_name: str) -> str:
    """Short sample text for voice preview."""
    return (
        f"Hello! This is a preview of the {voice_name} voice. "
        "Welcome to Texts to Audiobooks Creator, where your words come to life."
    )
