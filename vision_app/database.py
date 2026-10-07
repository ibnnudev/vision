import sqlite3, json, threading
from datetime import datetime, timezone
from typing import Optional, Dict, List
from config import settings

_lock = threading.Lock()

def _conn():
    c = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _lock:
        c = _conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS original_registry (
            listing_id TEXT PRIMARY KEY, model TEXT NOT NULL,
            price INTEGER NOT NULL, phash TEXT NOT NULL,
            dhash TEXT NOT NULL, whash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL, user_id TEXT NOT NULL,
            listing_title TEXT, price INTEGER, score INTEGER,
            status TEXT, action TEXT, details TEXT,
            ai_tier2_called INTEGER, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_log(status);
        """)
        c.commit(); c.close()

def add_original(listing_id, model, price, phash_hex, dhash_hex, whash_hex):
    with _lock:
        c = _conn()
        c.execute("""INSERT OR REPLACE INTO original_registry
            (listing_id, model, price, phash, dhash, whash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (listing_id, model, price, phash_hex, dhash_hex, whash_hex,
             datetime.now(timezone.utc).isoformat()))
        c.commit()
        count = c.execute("SELECT COUNT(*) FROM original_registry").fetchone()[0]
        c.close()
        return count

def get_all_originals() -> List[Dict]:
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM original_registry").fetchall()
        c.close()
        return [dict(r) for r in rows]

def log_audit(entry: Dict):
    with _lock:
        c = _conn()
        c.execute("""INSERT INTO audit_log
            (request_id, user_id, listing_title, price, score, status,
             action, details, ai_tier2_called, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry["request_id"], entry["user_id"], entry.get("listing_title"),
             entry.get("price"), entry["score"], entry["status"], entry["action"],
             json.dumps(entry.get("details", {})),
             1 if entry.get("ai_tier2_called") else 0,
             datetime.now(timezone.utc).isoformat()))
        c.commit(); c.close()

def get_stats() -> Dict:
    with _lock:
        c = _conn()
        total = c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        flagged = c.execute("SELECT COUNT(*) FROM audit_log WHERE status='FLAGGED_HIGH_RISK'").fetchone()[0]
        warning = c.execute("SELECT COUNT(*) FROM audit_log WHERE status='SUSPICIOUS'").fetchone()[0]
        safe = c.execute("SELECT COUNT(*) FROM audit_log WHERE status='SAFE'").fetchone()[0]
        ai_called = c.execute("SELECT COUNT(*) FROM audit_log WHERE ai_tier2_called=1").fetchone()[0]
        c.close()
    savings = ((total - ai_called) / total * 100) if total else 0
    return {"total_requests": total, "flagged": flagged, "warning": warning,
            "safe": safe, "ai_calls": ai_called,
            "api_savings_pct": round(savings, 1)}

def query_audit(limit: int = 20, status: Optional[str] = None):
    with _lock:
        c = _conn()
        if status:
            rows = c.execute("SELECT * FROM audit_log WHERE status=? ORDER BY id DESC LIMIT ?",
                             (status, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
