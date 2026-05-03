"""
app.py — Main Flask application for Texts to Audiobooks Creator.
"""
import os
import uuid
import hashlib
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import io
import json
import re
import zipfile

from flask import (Flask, render_template, request, jsonify,
                   send_file, redirect, url_for, abort, Response)

from db import init_db, get_db, get_setting, set_setting, get_project, update_project, get_recent_projects
from utils.parser import extract_text, detect_chapters, chunk_text
from utils.groq_utils import clean_text, generate_preview_text
from utils.tts import synthesize_chunk, synthesize_preview, VOICES
from utils.audio import merge_chunks

# ── App Setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "tts-audiobook-secret-2024")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Max 2 background workers
executor = ThreadPoolExecutor(max_workers=2)

# Cache: hash(text+voice) -> output filename
_audio_cache: dict[str, str] = {}
_cache_lock = threading.Lock()

init_db()


# ── Helpers ────────────────────────────────────────────────────────────────
def _cache_key(text: str, voice: str, speed: float) -> str:
    raw = f"{text}|{voice}|{speed}"
    return hashlib.md5(raw.encode()).hexdigest()


def _run_job(project_id: str):
    """Background job: synthesize audio for a project."""
    try:
        project = get_project(project_id)
        if not project:
            return

        text = project["text"]
        voice = project["voice"]
        speed = float(project.get("speed") or 1.0)
        style = project.get("style", "storytelling")

        # Check cache
        ck = _cache_key(text, voice, speed)
        with _cache_lock:
            cached = _audio_cache.get(ck)
        if cached and os.path.exists(os.path.join(OUTPUT_DIR, cached)):
            update_project(project_id, status="completed", progress=100, output_file=cached)
            return

        update_project(project_id, status="processing", progress=5)

        # AI clean text if small enough
        cleaned = clean_text(text, style)
        update_project(project_id, progress=10)

        # Chapter detection; fall back to paragraph-based sections
        raw_chapters = detect_chapters(cleaned)
        if len(raw_chapters) == 1 and len(cleaned) > 1500:
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', cleaned.strip()) if p.strip()]
            if len(paragraphs) > 2:
                sections, current = [], ""
                for para in paragraphs:
                    if len(current) + len(para) < 1500 or not current:
                        current = (current + "\n\n" + para).strip()
                    else:
                        sections.append(current)
                        current = para
                if current:
                    sections.append(current)
                if len(sections) > 1:
                    raw_chapters = sections

        # Build chapter → chunk map with friendly titles
        chapter_map = []  # [(title, [chunk_text, ...], preview)]
        for ch_idx, chapter in enumerate(raw_chapters):
            first_line = chapter.strip().split('\n')[0][:80].strip()
            if re.match(r'chapter\s+\w+', first_line, re.IGNORECASE):
                title = first_line.title()
            elif len(raw_chapters) == 1:
                title = "Full Audiobook"
            else:
                title = f"Part {ch_idx + 1}"
            chunks = chunk_text(chapter, max_chars=800)
            preview = chapter.strip()[:120]
            chapter_map.append((title, chunks, preview))

        all_chunks = [c for _, clist, _ in chapter_map for c in clist]
        total = len(all_chunks)
        chunk_files = []
        tmp_dir = os.path.join(OUTPUT_DIR, f"tmp_{project_id}")
        os.makedirs(tmp_dir, exist_ok=True)

        # Synthesize each chunk and collect duration_ms per chapter
        chunk_durations_ms = []
        for i, chunk in enumerate(all_chunks):
            chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
            duration_ms = synthesize_chunk(chunk, voice, speed, chunk_path)
            chunk_files.append(chunk_path)
            chunk_durations_ms.append(duration_ms)
            progress = 10 + int((i + 1) / total * 80)
            update_project(project_id, progress=progress)

        # Build chapter timestamps from accumulated chunk durations
        chapters_data = []
        running_ms = 0
        dur_idx = 0
        for title, clist, preview in chapter_map:
            ch_start_ms = running_ms
            for _ in clist:
                running_ms += chunk_durations_ms[dur_idx]
                dur_idx += 1
            chapters_data.append({
                "title": title,
                "start_s": round(ch_start_ms / 1000, 1),
                "preview": preview
            })

        update_project(project_id, progress=92)

        # Merge all chunks
        output_filename = f"{project_id}.mp3"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        merge_chunks(chunk_files, output_path)

        # Cleanup tmp dir
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

        # Store in cache
        with _cache_lock:
            _audio_cache[ck] = output_filename

        update_project(
            project_id,
            status="completed",
            progress=100,
            output_file=output_filename,
            chapters=json.dumps(chapters_data)
        )

    except Exception as e:
        update_project(project_id, status="failed", error_msg=str(e))
        print(f"[Job {project_id}] Error: {e}")


def _cleanup_old_files():
    """Delete uploads and outputs older than 3 days."""
    cutoff = time.time() - (3 * 24 * 3600)
    for directory in [UPLOAD_DIR, OUTPUT_DIR]:
        for fname in os.listdir(directory):
            fpath = os.path.join(directory, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                try:
                    os.remove(fpath)
                except OSError:
                    pass


# Run cleanup once at startup (non-blocking)
threading.Thread(target=_cleanup_old_files, daemon=True).start()


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", voices=list(VOICES.keys()))


@app.route("/dashboard")
def dashboard():
    is_admin = request.args.get("key") == ADMIN_KEY
    return render_template("dashboard.html", is_admin=is_admin)


@app.route("/listen/<project_id>")
def listen(project_id):
    project = get_project(project_id)
    if not project:
        abort(404)
    return render_template("listen.html", project=project)


# ── API ────────────────────────────────────────────────────────────────────

@app.route("/api/projects", methods=["GET"])
def api_projects():
    offset = int(request.args.get("offset", 0))
    projects = get_recent_projects(limit=10, offset=offset)
    return jsonify(projects)


@app.route("/api/project/<project_id>", methods=["GET"])
def api_project(project_id):
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Not found"}), 404
    return jsonify(project)


@app.route("/api/create", methods=["POST"])
def api_create():
    """Create a new audiobook project and queue it."""
    name = request.form.get("name", "").strip() or "Untitled Audiobook"
    voice = request.form.get("voice", list(VOICES.keys())[0])
    style = request.form.get("style", "storytelling")
    speed = float(request.form.get("speed", 1.0))
    text = request.form.get("text", "").strip()

    # Handle file upload
    file = request.files.get("file")
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".txt", ".pdf", ".docx"):
            return jsonify({"error": "Only .txt, .pdf, and .docx files are supported"}), 400
        fname = f"{uuid.uuid4()}{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        file.save(fpath)
        try:
            text = extract_text(fpath)
        except Exception as e:
            return jsonify({"error": f"Could not read file: {e}"}), 400
        finally:
            # Remove upload after extraction
            try:
                os.remove(fpath)
            except OSError:
                pass

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if voice not in VOICES:
        voice = list(VOICES.keys())[0]

    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute(
        "INSERT INTO projects (id,name,text,voice,style,speed,status,progress,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (project_id, name, text, voice, style, speed, "queued", 0, now)
    )
    conn.commit()
    conn.close()

    # Submit to background thread pool
    executor.submit(_run_job, project_id)

    return jsonify({"project_id": project_id, "status": "queued"})


@app.route("/api/project/<project_id>/delete", methods=["POST"])
def api_delete_project(project_id):
    """Admin-only: delete a project record and its output file."""
    if request.args.get("key") != ADMIN_KEY:
        abort(403)
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Not found"}), 404
    # Remove audio file if it exists
    if project.get("output_file"):
        path = os.path.join(OUTPUT_DIR, project["output_file"])
        try:
            os.remove(path)
        except OSError:
            pass
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/project/<project_id>/rename", methods=["POST"])
def api_rename_project(project_id):
    """Admin-only: rename a project."""
    if request.args.get("key") != ADMIN_KEY:
        abort(403)
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400
    if len(new_name) > 200:
        return jsonify({"error": "Name too long"}), 400
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Not found"}), 404
    conn = get_db()
    conn.execute("UPDATE projects SET name=? WHERE id=?", (new_name, project_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "name": new_name})


@app.route("/api/export-zip")
def api_export_zip():
    """Build a ZIP of all completed audiobooks and stream it."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, output_file FROM projects WHERE status='completed' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    completed = [(r["id"], r["name"], r["output_file"]) for r in rows
                 if r["output_file"] and os.path.exists(os.path.join(OUTPUT_DIR, r["output_file"]))]

    if not completed:
        return jsonify({"error": "No completed audiobooks to export"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for pid, name, fname in completed:
            safe = name.replace(" ", "_")[:50]
            src = os.path.join(OUTPUT_DIR, fname)
            zf.write(src, arcname=f"{safe}_{pid[:8]}.mp3")
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="audiobooks_export.zip",
        mimetype="application/zip"
    )


@app.route("/api/export-zip/count")
def api_export_zip_count():
    """Return count of completed exportable audiobooks."""
    conn = get_db()
    rows = conn.execute(
        "SELECT output_file FROM projects WHERE status='completed'"
    ).fetchall()
    conn.close()
    count = sum(
        1 for r in rows
        if r["output_file"] and os.path.exists(os.path.join(OUTPUT_DIR, r["output_file"]))
    )
    return jsonify({"count": count})


@app.route("/api/preview-voice", methods=["POST"])
def api_preview_voice():
    """Generate a short voice preview and stream it."""
    voice = request.json.get("voice", list(VOICES.keys())[0]) if request.is_json else request.form.get("voice")
    if voice not in VOICES:
        voice = list(VOICES.keys())[0]
    preview_text = generate_preview_text(voice)
    try:
        audio_bytes = synthesize_preview(voice, preview_text)
        return Response(audio_bytes, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-voice", methods=["POST"])
def api_upload_voice():
    """Store a custom voice sample file (placeholder for future cloning)."""
    file = request.files.get("voice_sample")
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".mp3", ".wav", ".ogg", ".m4a"):
        return jsonify({"error": "Audio files only (mp3, wav, ogg, m4a)"}), 400
    sample_id = str(uuid.uuid4())
    fname = f"voice_{sample_id}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    file.save(fpath)
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO voice_samples (id, filename, original_name, created_at) VALUES (?,?,?,?)",
        (sample_id, fname, file.filename, now)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Voice sample saved. Custom voice cloning is a future feature.", "id": sample_id})


@app.route("/download/<project_id>")
def download(project_id):
    """Stream the generated MP3 file as a download."""
    project = get_project(project_id)
    if not project or not project.get("output_file"):
        abort(404)
    path = os.path.join(OUTPUT_DIR, project["output_file"])
    if not os.path.exists(path):
        abort(404)
    safe_name = project["name"].replace(" ", "_")[:50] + ".mp3"
    return send_file(path, as_attachment=True, download_name=safe_name, mimetype="audio/mpeg")


@app.route("/stream/<project_id>")
def stream(project_id):
    """Stream audio for in-browser playback."""
    project = get_project(project_id)
    if not project or not project.get("output_file"):
        abort(404)
    path = os.path.join(OUTPUT_DIR, project["output_file"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="audio/mpeg", conditional=True)


# ── Admin ──────────────────────────────────────────────────────────────────

ADMIN_KEY = "julisunkan"

@app.route("/julisunkan", methods=["GET", "POST"])
def admin():
    if request.args.get("key") != ADMIN_KEY:
        abort(403)

    message = None
    if request.method == "POST":
        groq_key = request.form.get("groq_api_key", "").strip()
        hf_key = request.form.get("hf_api_key", "").strip()
        if groq_key:
            set_setting("groq_api_key", groq_key)
        if hf_key:
            set_setting("hf_api_key", hf_key)
        message = "Settings saved successfully."

    groq_key_set = bool(get_setting("groq_api_key"))
    hf_key_set = bool(get_setting("hf_api_key"))
    return render_template("admin.html", message=message,
                           groq_key_set=groq_key_set, hf_key_set=hf_key_set,
                           admin_key=ADMIN_KEY)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
