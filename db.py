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

    # Projects table
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
    existing = [r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()]
    if "chapters" not in existing:
        c.execute("ALTER TABLE projects ADD COLUMN chapters TEXT")

    # Settings table
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

    # Content reports table
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        details TEXT DEFAULT '',
        reporter_ip TEXT DEFAULT '',
        status TEXT DEFAULT 'open',
        reported_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
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


# ── Report helpers ──────────────────────────────────────────────────────────

def create_report(report_id, project_id, reason, details, reporter_ip, reported_at):
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (id, project_id, reason, details, reporter_ip, status, reported_at) "
        "VALUES (?,?,?,?,?,'open',?)",
        (report_id, project_id, reason, details, reporter_ip, reported_at)
    )
    conn.commit()
    conn.close()


def get_reports(status=None):
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT r.*, p.name as project_name, p.voice, p.status as project_status "
            "FROM reports r LEFT JOIN projects p ON r.project_id = p.id "
            "WHERE r.status=? ORDER BY r.reported_at DESC",
            (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT r.*, p.name as project_name, p.voice, p.status as project_status "
            "FROM reports r LEFT JOIN projects p ON r.project_id = p.id "
            "ORDER BY r.reported_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_open_report_count():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as n FROM reports WHERE status='open'").fetchone()
    conn.close()
    return row["n"] if row else 0


def resolve_report(report_id, resolved_at):
    conn = get_db()
    conn.execute(
        "UPDATE reports SET status='resolved', resolved_at=? WHERE id=?",
        (resolved_at, report_id)
    )
    conn.commit()
    conn.close()


def get_report_count_for_project(project_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as n FROM reports WHERE project_id=? AND status='open'",
        (project_id,)
    ).fetchone()
    conn.close()
    return row["n"] if row else 0


def get_recent_reports_by_ip(reporter_ip, since_iso):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as n FROM reports WHERE reporter_ip=? AND reported_at >= ?",
        (reporter_ip, since_iso)
    ).fetchone()
    conn.close()
    return row["n"] if row else 0
