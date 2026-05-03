# Texts to Audiobooks Creator

A full-stack web application that converts text and documents into MP3 audiobooks using AI-enhanced narration.

## Tech Stack
- **Backend**: Python 3.12, Flask 3.1.1
- **Database**: SQLite (database.db)
- **TTS Engine**: Microsoft Edge TTS (edge-tts) — 10 curated voices
- **AI Cleaning**: Groq API (llama-3.3-70b-versatile)
- **Audio Processing**: pydub (MP3 merge/compress at 64kbps)
- **Document Parsing**: pypdf, python-docx
- **Server**: gunicorn

## Project Structure
- `app.py` — Main Flask application, routes, background job runner
- `db.py` — SQLite init, CRUD helpers
- `utils/parser.py` — Text extraction from .txt/.pdf/.docx, chapter detection, chunking
- `utils/groq_utils.py` — Groq AI text cleaning (skipped if >5000 chars)
- `utils/tts.py` — Edge TTS synthesis with 10 voices + speed control
- `utils/audio.py` — Chunk merging and MP3 compression via pydub
- `templates/` — Jinja2 HTML templates (index, dashboard, listen, admin)
- `static/css/style.css` — Dark-themed responsive CSS
- `static/js/app.js` — Frontend JS (tabs, voice cards, progress polling, PWA)
- `static/manifest.json` + `static/service-worker.js` — PWA support

## Key Features
- Paste text or upload .txt, .pdf, .docx
- 10 voices (US/UK/AU/CA, male/female)
- Voice preview before generation
- AI text cleaning (storytelling / news / calm styles)
- Chapter detection + sentence-aware chunking (~800 chars/chunk)
- Background processing (max 2 workers), real-time progress polling
- Audio cache: hash(text+voice+speed) avoids reprocessing
- Shareable listen links: /listen/<project_id>
- Streaming download (send_file)
- PWA installable (manifest + service worker)
- Auto file cleanup after 3 days

## Admin
- Route: `/julisunkan?key=julisunkan`
- Configure Groq API key and optional HuggingFace key

## Running
- Start: `python -m gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`
- Port: 5000
