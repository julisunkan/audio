import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Projects table — each audiobook generation job
    c.execute("""CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        text TEXT NOT NULL,
        voice TEXT NOT NULL,
        style TEXT DEFAULT 'storytelling',
        speed REAL DEFAULT 1.0,
        status TEXT DEFAULT 'pending',
        progress INTEGER DEFAULT 0,
        output_file TEXT,
        error_msg TEXT,
        chapters TEXT,
        created_at TEXT NOT NULL
    )""")
    # Migrate: add chapters column if it doesn't exist yet
    existing = [r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()]
    if "chapters" not in existing:
        c.execute("ALTER TABLE projects ADD COLUMN chapters TEXT")

    # Settings table — stores API keys and config
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Uploaded voice samples
    c.execute("""CREATE TABLE IF NOT EXISTS voice_samples (
        id TEXT PRIMARY KEY,
        filename TEXT,
        original_name TEXT,
        created_at TEXT
    )""")

    conn.commit()
    conn.close()


def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def get_project(project_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_project(project_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [project_id]
    conn = get_db()
    conn.execute(f"UPDATE projects SET {fields} WHERE id=?", values)
    conn.commit()
    conn.close()


def get_recent_projects(limit=10, offset=0):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM projects ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
