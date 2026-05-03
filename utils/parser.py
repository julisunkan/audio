"""
parser.py — Extract plain text from .txt, .pdf, and .docx files.
"""
import os


def extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".txt":
        return _from_txt(filepath)
    elif ext == ".pdf":
        return _from_pdf(filepath)
    elif ext == ".docx":
        return _from_docx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _from_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _from_pdf(filepath: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _from_docx(filepath: str) -> str:
    from docx import Document
    doc = Document(filepath)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def detect_chapters(text: str) -> list[str]:
    """
    Split text by 'Chapter X' markers if present,
    otherwise return the text as a single chunk list.
    """
    import re
    pattern = re.compile(r'(chapter\s+\w+)', re.IGNORECASE)
    parts = pattern.split(text)
    if len(parts) <= 1:
        return [text]
    # Recombine: title + body
    chapters = []
    i = 1
    while i < len(parts):
        title = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        chapters.append(f"{title}\n{body}")
        i += 2
    return chapters


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """
    Split text into sentence-aware chunks of ~max_chars characters.
    Ensures we don't cut in the middle of a sentence.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence exceeds max_chars, hard-split it
            if len(sentence) > max_chars:
                for i in range(0, len(sentence), max_chars):
                    chunks.append(sentence[i:i + max_chars])
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks
