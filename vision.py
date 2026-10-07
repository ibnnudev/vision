#!/usr/bin/env python3
# ============================================================
# VISION — 3-Layer Triangle Fraud Detection API
# Single-file launcher for local development
# ============================================================
# Usage:
#   python vision.py             → show help
#   python vision.py setup       → install deps + write modules
#   python vision.py start       → start server (foreground)
#   python vision.py validate    → run validation suite (100 cases + charts)
#   python vision.py demo        → interactive upload demo
#   python vision.py all         → setup + start + validate
#   python vision.py stop        → stop server
# ============================================================

import sys
import os
import argparse
import subprocess
import time
import platform
import signal
import json
import shutil
from pathlib import Path

# ---------- CONFIG ----------
APP_NAME = "Vision"
APP_VERSION = "3.2.0"
APP_DIR = Path(__file__).parent.resolve()
MODULE_DIR = APP_DIR / "vision_app"
HOST = "127.0.0.1"
PORT = 8000
PID_FILE = APP_DIR / ".vision_server.pid"
IS_WINDOWS = platform.system() == "Windows"

# ---------- BANNER ----------
BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    ██╗   ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗                ║
║    ██║   ██║██║██╔════╝██║██╔═══██╗████╗  ██║                ║
║    ██║   ██║██║███████╗██║██║   ██║██╔██╗ ██║                ║
║    ╚██╗ ██╔╝██║╚════██║██║██║   ██║██║╚██╗██║                ║
║     ╚████╔╝ ██║███████║██║╚██████╔╝██║ ╚████║                ║
║      ╚═══╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝                ║
║                                                              ║
║    3-Layer Triangle Fraud Detection API                      ║
║    ──────────────────────────────────────                    ║
║    "See what others miss."                                   ║
║                                                              ║
║    Version: 3.2.0  ·  Local Edition                          ║
╚══════════════════════════════════════════════════════════════╝
"""

BANNER_COLOR = "\033[36m"  # Cyan
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"


def print_banner():
    """Print branded banner with color."""
    if IS_WINDOWS and not os.environ.get("WT_SESSION"):
        # Windows CMD tanpa ANSI support
        print(BANNER)
    else:
        print(f"{BANNER_COLOR}{BANNER}{RESET}")


def log(step: str, msg: str, status: str = "info"):
    icons = {"info": "•", "ok": "✓", "warn": "⚠", "err": "✗", "run": "→"}
    colors = {"ok": GREEN, "warn": YELLOW, "err": RED, "info": RESET, "run": RESET}
    c = colors.get(status, RESET)
    print(f"  {c}{icons.get(status, '•')}{RESET} [{step}] {msg}")


REQUIRED_PACKAGES = [
    # Core (wajib untuk server) — install cepat ~30s
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn[standard]"),
    ("PIL", "pillow"),
    ("imagehash", "imagehash"),
    ("multipart", "python-multipart"),
    ("rapidfuzz", "rapidfuzz"),
    ("cv2", "opencv-python-headless"),
    ("requests", "requests"),
]

VALIDATION_PACKAGES = [
    # Optional (untuk charts & metrics) — install ~2min
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
    ("sklearn", "scikit-learn"),
    ("statsmodels", "statsmodels"),
]

def check_and_install_deps(auto: bool = True, include_validation: bool = False):
    """Check installed packages, offer to install missing."""
    packages = REQUIRED_PACKAGES + (VALIDATION_PACKAGES if include_validation else [])
    log("DEPS", f"Checking {len(packages)} dependencies...", "run")
    missing = []
    for mod, pkg in packages:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if not missing:
        log("DEPS", f"All {len(packages)} packages installed", "ok")
        return True

    log("DEPS", f"Missing: {', '.join(missing)}", "warn")

    # Kalau auto mode — langsung install tanpa tanya
    if auto:
        log("DEPS", "Installing (auto)...", "run")
    else:
        ans = input(f"\n  Install {len(missing)} packages? [Y/n]: ").strip().lower()
        if ans and ans != "y":
            log("DEPS", "Skipped.", "warn")
            return False

    try:
        # Split batch biar keliatan progress
        for i, pkg in enumerate(missing, 1):
            log("DEPS", f"[{i}/{len(missing)}] Installing {pkg}...", "run")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", pkg],
                check=True,
            )
        log("DEPS", f"Installed {len(missing)} packages", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log("DEPS", f"Install failed: {e}", "err")
        return False

# ============================================================
# MODULE FILES (embedded)
# ============================================================
CONFIG_PY = '''import os

class Settings:
    HAMMING_THRESHOLD     = int(os.getenv("VISION_HAMMING_THRESHOLD", "10"))
    IMAGE_MATCH_MARGIN    = int(os.getenv("VISION_IMAGE_MATCH_MARGIN", "6"))
    SIFT_MIN_INLIERS      = int(os.getenv("VISION_SIFT_MIN_INLIERS", "8"))
    SIFT_RATIO            = float(os.getenv("VISION_SIFT_RATIO", "0.75"))
    PRICE_DROP_THRESHOLD  = float(os.getenv("VISION_PRICE_DROP", "40.0"))
    W_IMAGE = 40
    W_PRICE = 40
    W_NLP   = 40
    THRESHOLD_FLAGGED = 80
    THRESHOLD_WARNING = 40
    LLM_TIMEOUT_SEC   = 5.0
    LLM_PROVIDER      = os.getenv("LLM_PROVIDER", "auto")
    RATE_LIMIT_PER_MIN = 120
    API_KEY = os.getenv("VISION_API_KEY", "")
    DB_PATH = os.getenv("VISION_DB_PATH", "vision.db")

settings = Settings()

MARKET_PRICE_DB = {
    "honda brio 2021": 175_000_000,
    "honda brio rs 2021": 175_000_000,
    "honda brio satya 2021": 165_000_000,
    "toyota avanza 2020": 190_000_000,
    "toyota avanza g 2020": 195_000_000,
    "toyota avanza veloz 2020": 210_000_000,
}

TIER1_PATTERNS = [
    "jangan bahas harga", "jangan bahas", "gak usah bahas harga",
    "ga usah bahas harga", "jangan bhas harga",
    "bilang aja saudara", "bilang saudara", "aku saudaranya",
    "orang rumah", "jangan bilang", "jangan ketemu",
    "transfer dulu", "dp dulu", "saya di luar kota",
    "lagi di luar kota", "jangan tanya harga",
]
'''

DATABASE_PY = '''import sqlite3, json, threading
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
            image_blob BLOB,
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
        columns = {row[1] for row in c.execute("PRAGMA table_info(original_registry)")}
        if "image_blob" not in columns:
            c.execute("ALTER TABLE original_registry ADD COLUMN image_blob BLOB")
        c.commit(); c.close()

def add_original(listing_id, model, price, phash_hex, dhash_hex, whash_hex, image_blob=None):
    with _lock:
        c = _conn()
        c.execute("""INSERT OR REPLACE INTO original_registry
            (listing_id, model, price, phash, dhash, whash, image_blob, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (listing_id, model, price, phash_hex, dhash_hex, whash_hex,
             image_blob,
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
'''

LLM_CLIENT_PY = '''import os, asyncio, json
from typing import Dict, Optional
from config import settings, TIER1_PATTERNS

SYSTEM_PROMPT = """Anda adalah analis keamanan siber untuk marketplace kendaraan bekas di Indonesia.
Deteksi pola SOCIAL ENGINEERING (Triangle Fraud). Jawab HANYA JSON:
{"suspicious": true|false, "confidence": 0.0-1.0, "flagged_phrases": [...], "reasoning": "..."}"""

class LLMClient:
    def __init__(self):
        self.provider = None; self.client = None; self._init_provider()
    def _init_provider(self):
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.provider = "openai"; return
            except: pass
        self.provider = "heuristic"
    async def analyze(self, text: str) -> Dict:
        try:
            if self.provider == "openai":
                return await asyncio.wait_for(self._call_openai(text), timeout=settings.LLM_TIMEOUT_SEC)
            return await self._heuristic_fallback(text)
        except asyncio.TimeoutError:
            return {"suspicious": False, "provider": "timeout"}
        except Exception:
            return await self._heuristic_fallback(text)
    async def _call_openai(self, text: str) -> Dict:
        resp = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": f"Analisis: {text}"}],
            response_format={"type": "json_object"}, temperature=0.0)
        r = json.loads(resp.choices[0].message.content)
        r["provider"] = "openai"; return r
    async def _heuristic_fallback(self, text: str) -> Dict:
        await asyncio.sleep(0.02)
        hits = [p for p in TIER1_PATTERNS if p in text.lower()]
        return {"suspicious": len(hits) > 0, "confidence": 0.92 if hits else 0.10,
                "flagged_phrases": hits,
                "reasoning": "Pola triangle fraud terdeteksi." if hits else "Tidak ada indikasi.",
                "provider": "heuristic_fallback"}

_llm_client: Optional[LLMClient] = None
def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None: _llm_client = LLMClient()
    return _llm_client
'''

LAYERS_PY = '''import io, base64, json
from typing import List, Dict, Optional, Tuple
from PIL import Image
import imagehash
import cv2
import numpy as np
from rapidfuzz import fuzz
from config import settings, MARKET_PRICE_DB, TIER1_PATTERNS
from database import get_all_originals
from llm_client import get_llm_client

def b64_to_image(b64: str) -> Image.Image:
    if "," in b64: b64 = b64.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")

def compute_hashes(img: Image.Image) -> Dict[str, list]:
    """Hash overlapping regions so crops and partial overlays retain evidence."""
    w, h = img.size
    variants = [img]
    seen = {(0, 0, w, h)}
    for scale in (0.9, 0.75, 0.6, 0.45):
        cw, ch = max(32, int(w * scale)), max(32, int(h * scale))
        for row in range(3):
            for col in range(3):
                left = int((w - cw) * col / 2)
                top = int((h - ch) * row / 2)
                box = (left, top, left + cw, top + ch)
                if box not in seen:
                    seen.add(box)
                    variants.append(img.crop(box))
    hashes = {"phash": [], "dhash": [], "whash": []}
    for v in variants:
        hashes["phash"].append(str(imagehash.phash(v, hash_size=8)))
        hashes["dhash"].append(str(imagehash.dhash(v, hash_size=8)))
        hashes["whash"].append(str(imagehash.whash(v, hash_size=8)))
    return hashes

def hamming_hex(h1, h2):
    return int(imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2))

def _parse_stored(raw):
    if isinstance(raw, list): return raw
    try:
        p = json.loads(raw); return p if isinstance(p, list) else [p]
    except: return [raw]

def _match_distances(query_hashes, original):
    """Return cross-region distances, supporting old and new registry rows."""
    distances = []
    for name in ("phash", "dhash", "whash"):
        candidates = query_hashes[name]
        stored = _parse_stored(original[name])
        distances.append(min(hamming_hex(c, o) for c in candidates for o in stored))
    return distances

def _sift_match(query: Image.Image, original_blob):
    """SIFT descriptors + RANSAC homography for crop/overlay-resistant matches."""
    if not original_blob:
        return {"verified": False, "good_matches": 0, "inliers": 0}
    query_array = cv2.cvtColor(np.array(query), cv2.COLOR_RGB2GRAY)
    original_array = cv2.imdecode(np.frombuffer(original_blob, np.uint8), cv2.IMREAD_GRAYSCALE)
    if original_array is None:
        return {"verified": False, "good_matches": 0, "inliers": 0}
    sift = cv2.SIFT_create(nfeatures=1200)
    key_query, desc_query = sift.detectAndCompute(query_array, None)
    key_original, desc_original = sift.detectAndCompute(original_array, None)
    if desc_query is None or desc_original is None:
        return {"verified": False, "good_matches": 0, "inliers": 0}
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(desc_query, desc_original, k=2)
    good = [first for first, second in pairs
            if first.distance < settings.SIFT_RATIO * second.distance]
    if len(good) < settings.SIFT_MIN_INLIERS:
        return {"verified": False, "good_matches": len(good), "inliers": 0}
    source = np.float32([key_query[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    target = np.float32([key_original[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(source, target, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0
    return {"verified": inliers >= settings.SIFT_MIN_INLIERS,
            "good_matches": len(good), "inliers": inliers}

def layer1_image(image_b64_list):
    if not image_b64_list:
        return {"is_duplicate": False, "score": 0, "reason": "no_image", "images_analyzed": 0}
    originals = get_all_originals()
    if not originals:
        return {"is_duplicate": False, "score": 0, "reason": "empty_registry", "images_analyzed": 0}
    best_match = None; image_results = []
    for idx, b64 in enumerate(image_b64_list):
        try:
            img = b64_to_image(b64); hashes = compute_hashes(img)
        except Exception as e:
            image_results.append({"idx": idx, "error": str(e)}); continue
        per_image_best = None
        for orig in originals:
            dp, dd, dw = _match_distances(hashes, orig)
            feature_match = _sift_match(img, orig.get("image_blob"))
            ed = (dp + dd + dw) / 3
            support = sum(
                distance <= settings.HAMMING_THRESHOLD + settings.IMAGE_MATCH_MARGIN
                for distance in (dp, dd, dw)
            )
            if (per_image_best is None
                    or feature_match["verified"] and not per_image_best["feature_match"]["verified"]
                    or (feature_match["verified"] == per_image_best["feature_match"]["verified"]
                        and ed < per_image_best["ensemble_dist"])):
                per_image_best = {"idx": idx, "matched_listing_id": orig["listing_id"],
                                   "matched_model": orig["model"], "pHash_dist": dp,
                                   "dHash_dist": dd, "wHash_dist": dw,
                                   "ensemble_dist": round(ed, 2),
                                   "matched_variant_support": support,
                                   "feature_match": feature_match}
        if per_image_best and per_image_best["feature_match"]["verified"]:
            per_image_best["ensemble_dist"] = 0
        image_results.append(per_image_best or {"idx": idx, "error": "no_match"})
        if per_image_best and (best_match is None or per_image_best["ensemble_dist"] < best_match["ensemble_dist"]):
            best_match = per_image_best
    match_limit = settings.HAMMING_THRESHOLD + settings.IMAGE_MATCH_MARGIN
    if (best_match and (
            best_match["feature_match"]["verified"]
            or (best_match["ensemble_dist"] <= match_limit
                and best_match["matched_variant_support"] >= 2))):
        conf = max(0, (1 - best_match["ensemble_dist"]/64)) * 100
        return {"is_duplicate": True, "score": settings.W_IMAGE,
                "matched_listing_id": best_match["matched_listing_id"],
                "matched_model": best_match["matched_model"],
                "hamming_distance": best_match["ensemble_dist"],
                "pHash_dist": best_match["pHash_dist"], "dHash_dist": best_match["dHash_dist"],
                "wHash_dist": best_match["wHash_dist"],
                "matched_variant_support": best_match["matched_variant_support"],
                "match_strategy": ("sift_ransac" if best_match["feature_match"]["verified"]
                                   else "multi_region_ensemble"),
                "feature_match": best_match["feature_match"],
                "match_confidence": f"{conf:.1f}%", "images_analyzed": len(image_results)}
    return {"is_duplicate": False, "score": 0,
            "closest_hamming_distance": best_match["ensemble_dist"] if best_match else None,
            "images_analyzed": len(image_results)}

def fuzzy_find_model(title: str):
    tl = title.lower().strip(); best = (None, None, 0.0)
    for mk, p in MARKET_PRICE_DB.items():
        if mk in tl: return mk, p, 100.0
        s = fuzz.partial_ratio(mk, tl)
        if s > best[2]: best = (mk, p, s)
    return best if best[2] >= 75 else (None, None, best[2])

def layer2_price(title: str, price: int):
    mk, base, conf = fuzzy_find_model(title)
    if not base:
        return {"anomaly_detected": False, "score": 0, "reason": "model_not_in_db",
                "fuzzy_confidence": round(conf, 1)}
    drop = ((base - price) / base) * 100
    anomaly = drop >= settings.PRICE_DROP_THRESHOLD
    return {"anomaly_detected": anomaly, "score": settings.W_PRICE if anomaly else 0,
            "matched_model": mk, "baseline_price": base, "actual_price": price,
            "price_drop_percentage": f"{drop:.1f}%", "fuzzy_confidence": round(conf, 1)}

def tier1_nlp(text):
    return [p for p in TIER1_PATTERNS if p in text.lower()]

async def tier2_llm_call(text):
    return await get_llm_client().analyze(text)
'''

MAIN_PY = '''import uuid, time, json, base64, os
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from config import settings
from database import init_db, add_original, get_stats, query_audit, log_audit
from layers import (b64_to_image, compute_hashes, layer1_image, layer2_price,
                    tier1_nlp, tier2_llm_call)
from llm_client import get_llm_client

@asynccontextmanager
async def lifespan(app):
    init_db(); yield

app = FastAPI(title="Vision API", version="3.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_rate = defaultdict(list)
def check_rate(key):
    now = time.time()
    _rate[key] = [t for t in _rate[key] if now - t < 60]
    if len(_rate[key]) >= settings.RATE_LIMIT_PER_MIN: return False
    _rate[key].append(now); return True

@app.middleware("http")
async def mw(request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.req_id = req_id
    skip = ("/docs", "/openapi.json", "/redoc", "/health", "/", "/demo")
    if request.url.path not in skip:
        ip = request.client.host if request.client else "?"
        if not check_rate(ip):
            return JSONResponse(429, {"error": "rate_limit"})
    r = await call_next(request)
    r.headers["X-Request-ID"] = req_id
    return r

class ListingRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    listing_title: str = Field(..., min_length=3)
    price: int = Field(..., gt=0)
    description: str = ""
    chat_history: str = ""
    image_base64_list: List[str] = []
    image_hashes: List[str] = []

class SeedRequest(BaseModel):
    listing_id: str = Field(..., min_length=3)
    model: str = Field(..., min_length=3)
    price: int = Field(..., gt=0)
    image_base_64: str = Field(..., min_length=10)


def _to_python_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_to_python_types(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

@app.get("/")
def root():
    return {"service": "Vision API", "version": "3.2.0",
            "llm_provider": get_llm_client().provider, "docs": "/docs", "demo": "/demo"}

@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

@app.get("/stats")
def stats(): return get_stats()

@app.get("/audit")
def audit(limit: int = 20, status: Optional[str] = None):
    return {"entries": query_audit(limit=limit, status=status)}

@app.post("/api/v1/seed-original")
def seed_original(req: SeedRequest):
    img = b64_to_image(req.image_base_64)
    hashes = compute_hashes(img)
    count = add_original(req.listing_id, req.model, req.price,
                         json.dumps(hashes["phash"]), json.dumps(hashes["dhash"]),
                         json.dumps(hashes["whash"]),
                         base64.b64decode(req.image_base_64.split(",", 1)[-1]))
    return {"seeded": req.listing_id, "hashes": hashes, "total_registry": count}

async def _run_fraud_detect(req, req_id="internal"):
    score = 0; ai_triggered = False
    l1 = layer1_image(req.image_base64_list); score += l1["score"]
    l2 = layer2_price(req.listing_title, req.price); score += l2["score"]
    full_text = f"{req.listing_title}. {req.description} {req.chat_history}".strip()
    tier1_hits = tier1_nlp(full_text)
    trigger = bool(tier1_hits) or (score >= settings.THRESHOLD_FLAGGED)
    if trigger:
        ai_triggered = True
        t2 = await tier2_llm_call(full_text)
        if t2.get("suspicious"): score += settings.W_NLP
        l3 = {"tier1_hits": tier1_hits, "tier2_llm": t2, "ai_triggered": True,
              "trigger_reason": "tier1_hit" if tier1_hits else "score_high"}
    else:
        l3 = {"tier1_hits": tier1_hits, "tier2_llm": {"suspicious": False, "provider": "skipped"},
              "ai_triggered": False, "trigger_reason": "below_threshold"}
    if score >= settings.THRESHOLD_FLAGGED:
        status, action = "FLAGGED_HIGH_RISK", "PENDING_MANUAL_REVIEW"
    elif score >= settings.THRESHOLD_WARNING:
        status, action = "SUSPICIOUS", "WARNING_BANNER"
    else:
        status, action = "SAFE", "APPROVED"
    return _to_python_types({
        "request_id": req_id, "status": status, "fraud_score": score,
        "action_taken": action,
        "analysis_details": {"image_validation": l1, "price_validation": l2,
                              "text_ai_analysis": l3},
        "meta": {"ai_tier2_called": ai_triggered,
                 "weights": {"image": 40, "price": 40, "nlp": 40}},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

@app.post("/api/v1/fraud-detect/listings")
async def fraud_detect(req: ListingRequest, request: Request):
    res = await _run_fraud_detect(req, request.state.req_id)
    log_audit({"request_id": request.state.req_id, "user_id": req.user_id,
               "listing_title": req.listing_title, "price": req.price,
               "score": res["fraud_score"], "status": res["status"],
               "action": res["action_taken"], "details": res["analysis_details"],
               "ai_tier2_called": res["meta"]["ai_tier2_called"]})
    return res

@app.post("/api/v1/upload/seed")
async def upload_seed(listing_id: str = Form(...), model: str = Form(...),
                     price: int = Form(...), image: UploadFile = File(...)):
    raw = await image.read()
    img = b64_to_image(base64.b64encode(raw).decode())
    hashes = compute_hashes(img)
    count = add_original(listing_id, model, price,
                         json.dumps(hashes["phash"]), json.dumps(hashes["dhash"]),
                         json.dumps(hashes["whash"]), raw)
    return {"seeded": listing_id, "hashes": hashes, "total_registry": count}

@app.post("/api/v1/upload/detect")
async def upload_detect(user_id: str = Form(...), listing_title: str = Form(...),
                       price: int = Form(...), description: str = Form(""),
                       images: list[UploadFile] = File(...)):
    b64_list = [base64.b64encode(await f.read()).decode() for f in images]
    req = ListingRequest(user_id=user_id, listing_title=listing_title,
                        price=price, description=description, image_base64_list=b64_list)
    return await _run_fraud_detect(req, req_id="upload-multipart")

@app.get("/demo", response_class=HTMLResponse)
def demo_page():
    demo_path = os.path.join(os.path.dirname(__file__), "demo.html")
    if os.path.exists(demo_path):
        return open(demo_path, encoding="utf-8").read()
    return "<h1>demo.html missing</h1>"
'''

DEMO_HTML = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Vision Demo</title>
<style>
body{font-family:Inter,system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:24px;background:#f6f8fa;color:#1f2328}
h1{margin:0 0 4px;color:#0d1117}.sub{color:#656d76;margin-bottom:24px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:#fff;border:1px solid #d0d7de;border-radius:12px;padding:20px}
.card h2{font-size:16px;margin:0 0 12px;color:#0d1117}
label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}
input,textarea{width:100%;padding:8px 12px;border:1px solid #d0d7de;border-radius:6px;font-family:inherit;font-size:14px;box-sizing:border-box}
textarea{min-height:70px;resize:vertical}
.drop{border:2px dashed #d0d7de;border-radius:8px;padding:24px;text-align:center;color:#656d76;cursor:pointer;transition:all .2s;background:#fafbfc}
.drop:hover,.drop.active{border-color:#0969da;background:#f0f7ff}
.drop input{display:none}
.preview{display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:8px;margin-top:10px}
.preview img{width:100%;border-radius:6px;border:1px solid #d0d7de}
button{background:#1f883d;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-weight:600;font-size:14px;cursor:pointer;margin-top:14px;width:100%}
button:hover{background:#1a7f37}
button.secondary{background:#0969da}button.secondary:hover{background:#0860ca}
.result{margin-top:14px;padding:14px;border-radius:8px;font-size:12px;line-height:1.5;display:none;font-family:Menlo,monospace;white-space:pre-wrap;word-break:break-word}
.result.show{display:block}
.result.SAFE{background:#dafbe1;border:1px solid #1f883d;color:#1a7f37}
.result.SUSPICIOUS{background:#fff8c5;border:1px solid #bf8700;color:#7d4e00}
.result.FLAGGED_HIGH_RISK{background:#ffebe9;border:1px solid #cf222e;color:#a40e26}
</style></head><body>
<h1>&#x1F6E1;&#xFE0F; Vision Demo</h1>
<p class="sub">Upload foto asli &rarr; test deteksi penipuan segitiga (Triangle Fraud)</p>
<div class="grid">
  <div class="card">
    <h2>&#x1F4CC; Langkah 1: Daftarkan Foto Asli</h2>
    <label>Listing ID</label><input id="s_id" value="OLX-REAL-001">
    <label>Model</label><input id="s_model" value="Honda Brio 2021">
    <label>Harga Pasar (Rp)</label><input id="s_price" type="number" value="175000000">
    <label>Foto Asli</label>
    <div class="drop" id="s_drop"><input type="file" id="s_file" accept="image/*"><div>&#x1F4F7; Klik atau drag foto di sini</div></div>
    <div class="preview" id="s_prev"></div>
    <button class="secondary" onclick="seedSubmit()">Daftarkan Original</button>
    <div class="result" id="s_res"></div>
  </div>
  <div class="card">
    <h2>&#x1F9EA; Langkah 2: Test Iklan Mencurigakan</h2>
    <label>User ID</label><input id="t_user" value="USR-DEMO">
    <label>Judul</label><input id="t_title" value="Honda Brio 2021">
    <label>Harga Iklan</label><input id="t_price" type="number" value="85000000">
    <label>Deskripsi</label>
    <textarea id="t_desc">Jual cepat. Jangan bahas harga sama orang rumah ya, bilang aja saudara.</textarea>
    <label>Foto Listing (bisa multiple)</label>
    <div class="drop" id="t_drop"><input type="file" id="t_file" accept="image/*" multiple><div>&#x1F4F7; Klik atau drag foto</div></div>
    <div class="preview" id="t_prev"></div>
    <button onclick="testSubmit()">Deteksi Fraud</button>
    <div class="result" id="t_res"></div>
  </div>
</div>
<script>
function setupDrop(did,iid,pid){const d=document.getElementById(did),i=document.getElementById(iid),p=document.getElementById(pid);
d.onclick=()=>i.click();d.ondragover=e=>{e.preventDefault();d.classList.add('active')};
d.ondragleave=()=>d.classList.remove('active');
d.ondrop=e=>{e.preventDefault();d.classList.remove('active');i.files=e.dataTransfer.files;render(i,p)};
i.onchange=()=>render(i,p)}
function render(i,p){p.innerHTML='';[...i.files].slice(0,6).forEach(f=>{const im=document.createElement('img');im.src=URL.createObjectURL(f);p.appendChild(im)})}
setupDrop('s_drop','s_file','s_prev');setupDrop('t_drop','t_file','t_prev');
async function seedSubmit(){const f=document.getElementById('s_file').files[0];if(!f)return alert('Pilih foto!');
const fd=new FormData();fd.append('listing_id',s_id.value);fd.append('model',s_model.value);
fd.append('price',s_price.value);fd.append('image',f);
const r=await fetch('/api/v1/upload/seed',{method:'POST',body:fd});const j=await r.json();
const b=document.getElementById('s_res');b.className='result SAFE show';b.textContent='\\u2705 BERHASIL DAFTAR\\n'+JSON.stringify(j,null,2)}
async function testSubmit(){const files=document.getElementById('t_file').files;if(!files.length)return alert('Pilih foto!');
const fd=new FormData();fd.append('user_id',t_user.value);fd.append('listing_title',t_title.value);
fd.append('price',t_price.value);fd.append('description',t_desc.value);
[...files].forEach(f=>fd.append('images',f));
const r=await fetch('/api/v1/upload/detect',{method:'POST',body:fd});const j=await r.json();
const b=document.getElementById('t_res');b.className='result '+j.status+' show';
b.textContent=`Status: ${j.status}\\nScore: ${j.fraud_score}/120\\nAction: ${j.action_taken}\\n\\n${JSON.stringify(j.analysis_details,null,2)}`}
</script></body></html>'''

MODULES = {
    "config.py": CONFIG_PY,
    "database.py": DATABASE_PY,
    "llm_client.py": LLM_CLIENT_PY,
    "layers.py": LAYERS_PY,
    "main.py": MAIN_PY,
    "demo.html": DEMO_HTML,
}


def write_modules():
    """Write all module files to vision_app/."""
    MODULE_DIR.mkdir(exist_ok=True)
    log("SETUP", f"Writing modules to {MODULE_DIR.name}/", "run")
    for name, content in MODULES.items():
        path = MODULE_DIR / name
        path.write_text(content, encoding="utf-8")
        log("SETUP", f"  {name}", "ok")
    # __init__.py agar import sibling work
    (MODULE_DIR / "__init__.py").write_text("", encoding="utf-8")


# ============================================================
# PROCESS MANAGEMENT
# ============================================================
def is_server_running() -> bool:
    """Check if server running via health check."""
    try:
        import requests
        r = requests.get(f"http://{HOST}:{PORT}/health", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def stop_server():
    """Stop server (cross-platform)."""
    log("STOP", "Stopping server...", "run")

    # Try PID file first
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            log("STOP", "Server stopped (PID file)", "ok")
            return
        except Exception as e:
            log("STOP", f"PID file stale: {e}", "warn")

    # Fallback: kill by name
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"],
                           capture_output=True)
            subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq uvicorn*"],
                           capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "uvicorn.*main:app"],
                           capture_output=True)
        log("STOP", "Server stopped (by name)", "ok")
    except Exception as e:
        log("STOP", f"Fallback kill failed: {e}", "warn")


def start_server(background: bool = False, wait: bool = True) -> bool:
    """Start uvicorn server."""
    if is_server_running():
        log("START", f"Server already running at http://{HOST}:{PORT}", "ok")
        return True

    log("START", f"Starting server at http://{HOST}:{PORT}", "run")

    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", HOST, "--port", str(PORT),
        "--log-level", "warning",
    ]

    # Ensure PYTHONPATH includes MODULE_DIR
    env = os.environ.copy()
    env["PYTHONPATH"] = str(MODULE_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    if background:
        proc = subprocess.Popen(
            cmd, cwd=str(MODULE_DIR), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        PID_FILE.write_text(str(proc.pid))
    else:
        # Foreground — print and let user Ctrl+C
        print(f"\n  {GREEN}→ Server running at http://{HOST}:{PORT}{RESET}")
        print(f"  {GREEN}→ API docs:  http://{HOST}:{PORT}/docs{RESET}")
        print(f"  {GREEN}→ Demo UI:   http://{HOST}:{PORT}/demo{RESET}")
        print(f"  {GREEN}→ Press Ctrl+C to stop{RESET}\n")
        try:
            subprocess.run(cmd, cwd=str(MODULE_DIR), env=env)
        except KeyboardInterrupt:
            log("START", "Interrupted by user", "warn")
        return True

    # Wait for ready
    if wait:
        import requests
        for i in range(30):
            try:
                if requests.get(f"http://{HOST}:{PORT}/health", timeout=1).status_code == 200:
                    log("START", f"Server ready ({i+1}s)", "ok")
                    return True
            except Exception:
                time.sleep(1)
        log("START", "Server failed to become ready", "err")
        return False

    return True


# ============================================================
# COMMANDS
# ============================================================
def cmd_setup(args):
    print_banner()
    log("SETUP", f"Starting setup for {APP_NAME} v{APP_VERSION}", "run")
    # Core only (cepat)
    if not check_and_install_deps(auto=args.yes, include_validation=False):
        return 1
    write_modules()

    # Tanya apakah mau install validation packages (heavy)
    ans = input("\n  Install validation packages? (~2 min, ~500MB) [y/N]: ").strip().lower()
    if ans == "y":
        check_and_install_deps(auto=True, include_validation=True)

    log("SETUP", "Setup complete", "ok")
    print(f"\n  Next: python vision.py start")
    return 0


def cmd_start(args):
    """Start server (foreground by default)."""
    print_banner()
    if not (MODULE_DIR / "main.py").exists():
        log("START", "Modules not found. Run setup first:", "err")
        print(f"  {YELLOW}python vision.py setup{RESET}")
        return 1
    ok = start_server(background=args.daemon)
    if args.daemon and ok:
        print(f"\n  {GREEN}Server running in background (PID: {PID_FILE.read_text().strip()}){RESET}")
        print(f"  {GREEN}Demo UI: http://{HOST}:{PORT}/demo{RESET}")
        print(f"  {GREEN}Stop:    python vision.py stop{RESET}")
    return 0 if ok else 1


def cmd_stop(args):
    """Stop background server."""
    print_banner()
    stop_server()
    return 0


def cmd_validate(args):
    """Run full validation suite."""
    print_banner()
    log("VALIDATE", "Running validation suite (n=24 cases + charts)", "run")

    # Ensure server running
    if not is_server_running():
        log("VALIDATE", "Server not running. Starting in background...", "warn")
        write_modules()
        if not start_server(background=True, wait=True):
            log("VALIDATE", "Cannot start server", "err")
            return 1

    # Write validation script and run it
    val_script = MODULE_DIR / "_validate.py"
    val_script.write_text(VALIDATION_SCRIPT, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(MODULE_DIR)

    try:
        subprocess.run([sys.executable, str(val_script)],
                       cwd=str(MODULE_DIR), env=env, check=True)
    except subprocess.CalledProcessError as e:
        log("VALIDATE", f"Validation failed: {e}", "err")
        return 1

    log("VALIDATE", f"Charts saved to {MODULE_DIR}/", "ok")
    return 0


def cmd_demo(args):
    """Interactive upload demo (prompts for image paths)."""
    print_banner()
    log("DEMO", "Interactive demo — you'll be prompted for image paths", "run")

    if not is_server_running():
        log("DEMO", "Server not running. Starting in background...", "warn")
        write_modules()
        if not start_server(background=True, wait=True):
            return 1

    import base64
    import requests

    def ask_path(prompt: str) -> str:
        while True:
            p = input(f"\n  {prompt}\n  Path: ").strip().strip('"').strip("'")
            if os.path.exists(p):
                return p
            print(f"  {RED}File not found: {p}{RESET}")

    print(f"\n  {BOLD}STEP 1 — Register original (photo of legit seller){RESET}")
    orig_path = ask_path("Upload path ke foto ASLI (yang mau dilindungi):")
    orig_b64 = base64.b64encode(open(orig_path, "rb").read()).decode()
    r = requests.post(f"http://{HOST}:{PORT}/api/v1/seed-original", json={
        "listing_id": "OLX-REAL-001",
        "model": "Honda Brio 2021",
        "price": 175_000_000,
        "image_base_64": orig_b64,
    })
    log("DEMO", f"Registered: {r.json()['total_registry']} original(s)", "ok")

    while True:
        print(f"\n  {BOLD}STEP 2 — Test listing{RESET}")
        test_path = ask_path("Upload path ke foto TEST (bisa sama / beda):")
        test_b64 = base64.b64encode(open(test_path, "rb").read()).decode()

        title = input("  Judul listing [Honda Brio 2021]: ").strip() or "Honda Brio 2021"
        price_str = input("  Harga [85000000]: ").strip() or "85000000"
        desc = input("  Deskripsi [Jual cepat. Jangan bahas harga sama orang rumah ya, bilang aja saudara.]: ").strip()
        if not desc:
            desc = "Jual cepat. Jangan bahas harga sama orang rumah ya, bilang aja saudara."

        r = requests.post(f"http://{HOST}:{PORT}/api/v1/fraud-detect/listings", json={
            "user_id": "USR-DEMO",
            "listing_title": title,
            "price": int(price_str),
            "description": desc,
            "image_base64_list": [test_b64],
        })
        res = r.json()
        print(f"\n  {'='*60}")
        print(f"  Status       : {BOLD}{res['status']}{RESET}")
        print(f"  Fraud Score  : {res['fraud_score']}/120")
        print(f"  Action       : {res['action_taken']}")
        iv = res['analysis_details']['image_validation']
        pv = res['analysis_details']['price_validation']
        l3 = res['analysis_details']['text_ai_analysis']
        print(f"  L1 (image)   : dup={iv.get('is_duplicate')}, dist={iv.get('hamming_distance', iv.get('closest_hamming_distance'))}")
        print(f"  L2 (price)   : anomaly={pv.get('anomaly_detected')}, drop={pv.get('price_drop_percentage')}")
        print(f"  L3 (NLP)     : tier1_hits={len(l3.get('tier1_hits', []))}, ai_called={res['meta']['ai_tier2_called']}")
        print(f"  {'='*60}")

        again = input("\n  Test lagi? [y/N]: ").strip().lower()
        if again != "y":
            break

    return 0


def cmd_all(args):
    """Full pipeline: setup → start → validate."""
    print_banner()
    log("ALL", "Full pipeline: setup → start → validate", "run")
    if not check_and_install_deps(auto=args.yes):
        return 1
    write_modules()
    if not start_server(background=True, wait=True):
        return 1

    # Run validation
    val_script = MODULE_DIR / "_validate.py"
    val_script.write_text(VALIDATION_SCRIPT, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(MODULE_DIR)

    try:
        subprocess.run([sys.executable, str(val_script)],
                       cwd=str(MODULE_DIR), env=env, check=True)
    except subprocess.CalledProcessError as e:
        log("ALL", f"Validation failed: {e}", "err")
        return 1

    print(f"\n  {GREEN}{BOLD}Pipeline complete!{RESET}")
    print(f"  {GREEN}→ Server:    http://{HOST}:{PORT}/demo{RESET}")
    print(f"  {GREEN}→ Charts:    {MODULE_DIR}/validation_dashboard.png{RESET}")
    print(f"  {GREEN}→ Stop:      python vision.py stop{RESET}")
    return 0


# ============================================================
# VALIDATION SCRIPT (embedded)
# ============================================================
VALIDATION_SCRIPT = r'''"""Vision — Validation Suite (auto-generated)"""
import subprocess, sys, time, io, base64, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
import pandas as pd
import requests

BASE = "http://127.0.0.1:8000"

def request_json(method, url, **kwargs):
    response = requests.request(method, url, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        body = response.text.strip().replace("\n", " ")[:500]
        raise RuntimeError(
            f"{method} {url} returned HTTP {response.status_code} "
            f"with non-JSON response: {body!r}"
        ) from exc
    if not response.ok:
        raise RuntimeError(
            f"{method} {url} returned HTTP {response.status_code}: {payload}"
        )
    return payload

# ---------- GENERATORS ----------
def make_car(seed, size=(400, 300)):
    rng = np.random.default_rng(seed)
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    scene_type = seed % 4
    if scene_type == 0:
        for y in range(h):
            arr[y, :] = [int(100 + y*0.5), int(150 + y*0.3), int(200 + y*0.1)]
        arr[160:230, 50:350] = [220, 50, 50]
        arr[140:170, 120:280] = [180, 30, 30]
        arr[170:200, 100:150] = [130, 180, 220]
        arr[170:200, 250:300] = [130, 180, 220]
        arr[220:245, 80:130] = [30, 30, 30]
        arr[220:245, 270:320] = [30, 30, 30]
        arr[40:80, 320:360] = [255, 240, 100]
    elif scene_type == 1:
        arr[:] = [40, 50, 70]
        arr[180:240, 60:340] = [60, 120, 200]
        arr[150:180, 100:300] = [80, 150, 230]
        arr[160:180, 120:180] = [200, 220, 240]
        arr[160:180, 220:280] = [200, 220, 240]
        arr[235:260, 90:140] = [20, 20, 20]
        arr[235:260, 260:310] = [20, 20, 20]
        arr[260:, :] = [60, 55, 50]
    elif scene_type == 2:
        arr[:] = [200, 220, 240]
        arr[180:, :] = [80, 140, 60]
        arr[140:200, 40:360] = [230, 210, 60]
        arr[110:145, 100:300] = [200, 180, 40]
        arr[120:145, 130:180] = [150, 200, 230]
        arr[120:145, 220:270] = [150, 200, 230]
        arr[195:225, 70:120] = [25, 25, 25]
        arr[195:225, 280:330] = [25, 25, 25]
    else:
        arr[:] = [20, 20, 40]
        arr[200:250, 80:320] = [60, 160, 80]
        arr[170:205, 130:270] = [50, 140, 70]
        arr[180:200, 150:200] = [180, 220, 240]
        arr[180:200, 220:260] = [180, 220, 240]
        arr[245:270, 110:160] = [15, 15, 15]
        arr[245:270, 250:300] = [15, 15, 15]
        for _ in range(20):
            x, y = rng.integers(0, w), rng.integers(0, 100)
            arr[y, x] = [255, 255, 200]
    noise = rng.integers(-10, 10, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def to_b64(img, quality=95):
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()

def transform(img, kind):
    if kind == "none": return img
    if kind == "compress30": return Image.open(io.BytesIO(base64.b64decode(to_b64(img, 30))))
    if kind == "compress50": return Image.open(io.BytesIO(base64.b64decode(to_b64(img, 50))))
    if kind == "crop10":
        w, h = img.size; return img.crop((int(w*0.05), int(h*0.05), int(w*0.95), int(h*0.95)))
    if kind == "crop20":
        w, h = img.size; return img.crop((int(w*0.1), int(h*0.1), int(w*0.9), int(h*0.9)))
    if kind == "watermark":
        i2 = img.copy(); ImageDraw.Draw(i2).text((20, 20), "OLX COPY", fill=(255, 0, 0)); return i2
    if kind == "brightness":
        return ImageEnhance.Brightness(img).enhance(1.3)
    return img

# ---------- PREPARE ----------
print("\n  [1/5] Generating test images...")
BASE_BRIO   = make_car(seed=42)
BASE_AVANZA = make_car(seed=88)
BASE_SUV    = make_car(seed=33)
BASE_SEDAN  = make_car(seed=77)

import imagehash
d1 = imagehash.phash(BASE_BRIO, hash_size=8) - imagehash.phash(BASE_AVANZA, hash_size=8)
d2 = imagehash.phash(BASE_BRIO, hash_size=8) - imagehash.phash(BASE_SUV, hash_size=8)
print(f"      pHash distance BRIO vs AVANZA: {d1}")
print(f"      pHash distance BRIO vs SUV   : {d2}")
assert d1 > 10 and d2 > 10, "Generator failed!"
print("      Generator OK")

# Re-init by hitting endpoint (will auto-create)
time.sleep(1)

# Register ONLY BRIO
print("\n  [2/5] Registering ONLY BRIO as protected...")
seed_result = request_json("POST", f"{BASE}/api/v1/seed-original", json={
    "listing_id": "OLX-PROTECTED-BRIO-001",
    "model": "Honda Brio 2021",
    "price": 175_000_000,
    "image_base_64": to_b64(BASE_BRIO),
})
print(f"      Registry: {seed_result['total_registry']} original(s)")

# ---------- BUILD TEST CASES ----------
print("\n  [3/5] Building test cases...")
P_BRIO = 175_000_000
P_AVANZA = 190_000_000
DFRAUD = "Jual cepat. Jangan bahas harga sama orang rumah ya, bilang aja saudara."
DNORM  = "Pajak hidup, surat lengkap, nego halus. Mobil terawat, siap cek."
DBU    = "BU cepat banting harga, pajak hidup, nego halus."
DPARAPHRASE = "Mobil siap cek langsung. Nanti ngobrol sama ibu saya aja ya, saya lagi keluar kota."

cases = []
def add(cat, exp, img, tk, title, price, desc, notes):
    cases.append({"cat":cat,"expected":exp,"base":img,"tk":tk,"title":title,
                   "price":price,"desc":desc,"notes":notes})

for tk in ["none","compress30","compress50","crop10","crop20","watermark","brightness"]:
    add("fraud_stolen", 1, BASE_BRIO, tk, "Honda Brio 2021", int(P_BRIO*0.5), DFRAUD, f"stolen+{tk}")
for tk in ["none","compress30"]:
    add("fraud_paraphrase", 1, BASE_BRIO, tk, "Honda Brio 2021", int(P_BRIO*0.5), DPARAPHRASE, f"paraphrase+{tk}")
add("fraud_typo", 1, BASE_BRIO, "none", "Honda Brio 2021", int(P_BRIO*0.5),
    "Jngn bhs hrga sma orng rmh, blng aja sodara.", "typo")
add("fraud_image_only", 1, BASE_BRIO, "none", "Honda Brio 2021", P_BRIO, DNORM, "image_only")

for tk in ["none","compress50","crop10","brightness"]:
    add("normal_avanza", 0, BASE_AVANZA, tk, "Toyota Avanza 2020", P_AVANZA, DNORM, f"avanza+{tk}")
for tk in ["none","compress50"]:
    add("normal_suv", 0, BASE_SUV, tk, "Honda Brio 2021", P_BRIO, DNORM, f"suv+{tk}")
for tk in ["none","compress50"]:
    add("normal_sedan", 0, BASE_SEDAN, tk, "Toyota Avanza 2020", P_AVANZA, DNORM, f"sedan+{tk}")
for tk in ["none","compress50"]:
    add("normal_bu", 0, BASE_AVANZA, tk, "Toyota Avanza 2020", int(P_AVANZA*0.58), DBU, f"BU_avanza+{tk}")
add("normal_bu", 0, BASE_SUV, "none", "Honda Brio 2021", int(P_BRIO*0.5), DBU, "BU_suv")
add("boundary_drop39", 0, BASE_AVANZA, "none", "Toyota Avanza 2020", int(P_AVANZA*0.61), DNORM, "drop39")
add("boundary_drop40", 1, BASE_BRIO, "none", "Honda Brio 2021", int(P_BRIO*0.60), DNORM, "drop40")

print(f"      Total: {len(cases)} cases")

# ---------- RUN ----------
print(f"\n  [4/5] Running {len(cases)} cases...")
results = []
t0 = time.time()
for i, c in enumerate(cases):
    try:
        img = transform(c["base"], c["tk"])
        res = request_json("POST", f"{BASE}/api/v1/fraud-detect/listings", json={
            "user_id": f"U{i:03d}", "listing_title": c["title"], "price": c["price"],
            "description": c["desc"], "image_base64_list": [to_b64(img)],
        }, timeout=10)
        iv = res['analysis_details']['image_validation']
        pv = res['analysis_details']['price_validation']
        l3 = res['analysis_details']['text_ai_analysis']
        results.append({
            "id": f"T{i+1:03d}", "cat": c["cat"], "expected": c["expected"],
            "status": res['status'], "score": res['fraud_score'],
            "predicted": 1 if res['fraud_score'] >= 80 else 0,
            "L1_dup": iv.get('is_duplicate', False),
            "L1_dist": iv.get('hamming_distance', iv.get('closest_hamming_distance')),
            "L2_anomaly": pv.get('anomaly_detected', False),
            "L3_tier1": len(l3.get('tier1_hits', [])),
            "L3_ai": res['meta']['ai_tier2_called'],
            "notes": c["notes"],
        })
    except Exception as e:
        print(f"      {c.get('notes','?')}: {e}")

df = pd.DataFrame(results)
df.to_csv("validation_results.csv", index=False)
elapsed = time.time()-t0
print(f"      Done in {elapsed:.1f}s (avg {elapsed/len(df)*1000:.0f}ms)")

# ---------- METRICS ----------
from statsmodels.stats.proportion import proportion_confint

TP = ((df['expected']==1) & (df['predicted']==1)).sum()
TN = ((df['expected']==0) & (df['predicted']==0)).sum()
FP = ((df['expected']==0) & (df['predicted']==1)).sum()
FN = ((df['expected']==1) & (df['predicted']==0)).sum()

def wci(s, n, alpha=0.05):
    if n == 0: return (0, 0)
    lo, hi = proportion_confint(s, n, alpha=alpha, method='wilson')
    return round(lo*100, 1), round(hi*100, 1)

prec = TP/(TP+FP) if (TP+FP) else 0
rec  = TP/(TP+FN) if (TP+FN) else 0
f1   = 2*prec*rec/(prec+rec) if (prec+rec) else 0
acc  = (TP+TN)/len(df)
fpr  = FP/(FP+TN) if (FP+TN) else 0
fnr  = FN/(FN+TP) if (FN+TP) else 0
spec = TN/(TN+FP) if (TN+FP) else 0

print("\n  " + "="*60)
print(f"   METRICS (n={len(df)}, threshold=80)")
print("  " + "="*60)
print(f"  TP={TP}  TN={TN}  FP={FP}  FN={FN}")
print(f"  Precision  : {prec*100:5.1f}%  [CI: {wci(TP,TP+FP)[0]}-{wci(TP,TP+FP)[1]}%]")
print(f"  Recall     : {rec*100:5.1f}%  [CI: {wci(TP,TP+FN)[0]}-{wci(TP,TP+FN)[1]}%]")
print(f"  F1-Score   : {f1:.3f}")
print(f"  Accuracy   : {acc*100:5.1f}%")
print(f"  FPR        : {fpr*100:5.1f}%")
print(f"  FNR        : {fnr*100:5.1f}%")
print("  " + "="*60)

# Save summary
summary = {
    "n": len(df), "threshold": 80,
    "TP": int(TP), "TN": int(TN), "FP": int(FP), "FN": int(FN),
    "precision": round(prec*100,1), "recall": round(rec*100,1), "f1": round(f1,3),
    "accuracy": round(acc*100,1), "specificity": round(spec*100,1),
    "fpr": round(fpr*100,1), "fnr": round(fnr*100,1),
    "precision_ci": wci(TP, TP+FP), "recall_ci": wci(TP, TP+FN),
}
with open("validation_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ---------- CHARTS ----------
print("\n  [5/5] Generating charts...")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.gridspec import GridSpec
from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score
from PIL import Image as PILImage

# Inter font
try:
    from matplotlib import font_manager
    fd = os.path.join(os.path.dirname(__file__), ".fonts")
    os.makedirs(fd, exist_ok=True)
    fpath = os.path.join(fd, "Inter-var.ttf")
    # Download 4 static weights
    weights = {
        "Inter-Regular.ttf":  "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Regular.ttf",
        "Inter-Medium.ttf":   "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Medium.ttf",
        "Inter-SemiBold.ttf": "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-SemiBold.ttf",
        "Inter-Bold.ttf":     "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Bold.ttf",
    }
    import urllib.request
    for fname, url in weights.items():
        fpath = os.path.join(fd, fname)
        if not os.path.exists(fpath):
            try:
                urllib.request.urlretrieve(url, fpath)
            except Exception:
                pass
        font_manager.fontManager.addfont(fpath)
    plt.rcParams['font.family'] = 'Inter'
    plt.rcParams['font.sans-serif'] = ['Inter', 'DejaVu Sans']
except Exception:
    pass
plt.rcParams['axes.unicode_minus'] = False

# Mega dashboard
fig = plt.figure(figsize=(22, 14))
fig.suptitle("Vision Validation Report — Complete Dashboard",
              fontsize=22, fontweight='bold', y=0.995)
gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3,
               top=0.94, bottom=0.06, left=0.05, right=0.97)

ax1 = fig.add_subplot(gs[0, 0])
fpr_c, tpr_c, _ = roc_curve(df['expected'], df['score'])
roc_auc = auc(fpr_c, tpr_c)
ax1.plot(fpr_c, tpr_c, 'b-', linewidth=2.5, label=f'AUC = {roc_auc:.3f}')
ax1.plot([0,1], [0,1], 'k--', alpha=0.5)
ax1.fill_between(fpr_c, tpr_c, alpha=0.15, color='blue')
ax1.set_xlabel('False Positive Rate', fontsize=11, fontweight='bold')
ax1.set_ylabel('True Positive Rate', fontsize=11, fontweight='bold')
ax1.set_title('ROC Curve', fontsize=13, fontweight='bold')
ax1.legend(loc='lower right'); ax1.grid(alpha=0.3)

ax2 = fig.add_subplot(gs[0, 1])
prec_c, rec_c, _ = precision_recall_curve(df['expected'], df['score'])
ap = average_precision_score(df['expected'], df['score'])
ax2.plot(rec_c, prec_c, 'g-', linewidth=2.5, label=f'AP = {ap:.3f}')
ax2.axhline(df['expected'].mean(), color='k', linestyle='--', alpha=0.5)
ax2.set_xlabel('Recall', fontsize=11, fontweight='bold')
ax2.set_ylabel('Precision', fontsize=11, fontweight='bold')
ax2.set_title('Precision-Recall Curve', fontsize=13, fontweight='bold')
ax2.legend(loc='lower left'); ax2.grid(alpha=0.3)

ax3 = fig.add_subplot(gs[0, 2])
ax3.axis('off')
metrics_data = [
    ["Metric", "Value", "95% CI"],
    ["n (total)", f"{len(df)}", "—"],
    ["TP/TN/FP/FN", f"{TP}/{TN}/{FP}/{FN}", "—"],
    ["Precision", f"{prec*100:.1f}%", f"[{wci(TP,TP+FP)[0]}, {wci(TP,TP+FP)[1]}]"],
    ["Recall", f"{rec*100:.1f}%", f"[{wci(TP,TP+FN)[0]}, {wci(TP,TP+FN)[1]}]"],
    ["F1-Score", f"{f1:.3f}", "—"],
    ["Accuracy", f"{acc*100:.1f}%", "—"],
    ["Specificity", f"{spec*100:.1f}%", "—"],
    ["FPR", f"{fpr*100:.1f}%", "—"],
    ["FNR", f"{fnr*100:.1f}%", "—"],
]
t = ax3.table(cellText=metrics_data, loc='center', cellLoc='center',
               colWidths=[0.42, 0.28, 0.3])
t.auto_set_font_size(False); t.set_fontsize(11); t.scale(1, 2.2)
for i in range(3):
    t[(0, i)].set_facecolor('#34495e')
    t[(0, i)].set_text_props(color='white', weight='bold')
ax3.set_title('Performance Metrics', fontsize=13, fontweight='bold', pad=12)

ax4 = fig.add_subplot(gs[1, 0])
cm = np.array([[TN, FP], [FN, TP]])
labels = np.array([[f"TN={TN}", f"FP={FP}"], [f"FN={FN}", f"TP={TP}"]])
sns.heatmap(cm, annot=labels, fmt='', cmap='RdYlGn', cbar=False, ax=ax4,
            xticklabels=['Pred Safe', 'Pred Fraud'],
            yticklabels=['Actual Safe', 'Actual Fraud'],
            annot_kws={"size": 15, "weight": "bold"},
            linewidths=3, linecolor='white', vmin=0, vmax=max(1, max(TP,TN)))
ax4.set_title(f'Confusion Matrix', fontsize=13, fontweight='bold')

ax5 = fig.add_subplot(gs[1, 1])
df['b_naive'] = df['L2_anomaly'].astype(int)
df['b_regex'] = (df['L3_tier1'] > 0).astype(int)
df['b_phash'] = df['L1_dup'].astype(int)

def eval_m(y, p):
    tp=((y==1)&(p==1)).sum(); tn=((y==0)&(p==0)).sum()
    fp=((y==0)&(p==1)).sum(); fn=((y==1)&(p==0)).sum()
    pr=tp/(tp+fp) if (tp+fp) else 0; rc=tp/(tp+fn) if (tp+fn) else 0
    f = 2*pr*rc/(pr+rc) if (pr+rc) else 0
    return pr*100, rc*100, f*100

methods = ["Vision", "Naive Price", "Regex", "pHash"]
data_m = [eval_m(df['expected'], df['predicted']),
          eval_m(df['expected'], df['b_naive']),
          eval_m(df['expected'], df['b_regex']),
          eval_m(df['expected'], df['b_phash'])]
x = np.arange(len(methods)); w = 0.25
for i, (label, color) in enumerate([('P','#3498db'),('R','#2ecc71'),('F1','#9b59b6')]):
    vals = [d[i] for d in data_m]
    bars = ax5.bar(x + i*w, vals, w, label=label, color=color, edgecolor='black')
    for bar, v in zip(bars, vals):
        ax5.text(bar.get_x()+bar.get_width()/2, v+1.5, f'{v:.0f}',
                  ha='center', fontsize=9, fontweight='bold')
ax5.set_xticks(x + w); ax5.set_xticklabels(methods, fontsize=10)
ax5.set_ylabel('Value (%)', fontsize=11, fontweight='bold')
ax5.set_title('Baseline Comparison', fontsize=13, fontweight='bold')
ax5.legend(fontsize=10); ax5.grid(axis='y', alpha=0.3); ax5.set_ylim(0, 115)

ax6 = fig.add_subplot(gs[1, 2])
sc = {'SAFE':'#2ecc71', 'SUSPICIOUS':'#f39c12', 'FLAGGED_HIGH_RISK':'#e74c3c'}
order = df.sort_values('score').reset_index(drop=True)
colors_ = [sc.get(s, '#95a5a6') for s in order['status']]
ax6.barh(range(len(order)), order['score'], color=colors_, edgecolor='black', linewidth=0.5)
ax6.axvline(40, color='orange', linestyle='--', linewidth=2, alpha=0.8)
ax6.axvline(80, color='red', linestyle='--', linewidth=2, alpha=0.8)
ax6.set_yticks([]); ax6.set_xlabel('Fraud Score', fontsize=11, fontweight='bold')
ax6.set_title(f'Score Distribution (n={len(df)})', fontsize=13, fontweight='bold')
ax6.grid(axis='x', alpha=0.3)

plt.savefig("validation_dashboard.png", dpi=180, bbox_inches='tight', facecolor='white')
plt.close()
print("      validation_dashboard.png")

# Vertical poster
charts = ["validation_roc_pr.png", "validation_baselines.png",
          "validation_confusion.png", "validation_scores.png"]

# Save individual charts
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(fpr_c, tpr_c, 'b-', linewidth=2.5, label=f'AUC = {roc_auc:.3f}')
ax.plot([0,1], [0,1], 'k--', alpha=0.5)
ax.set_xlabel('FPR'); ax.set_ylabel('TPR'); ax.set_title('ROC')
ax.legend(); ax.grid(alpha=0.3)
plt.savefig("validation_roc_pr.png", dpi=150, bbox_inches='tight')
plt.close()

print("\n  Validation complete!")
print(f"   Files saved in: {os.path.dirname(os.path.abspath('validation_dashboard.png'))}")
print(f"     - validation_results.csv")
print(f"     - validation_summary.json")
print(f"     - validation_dashboard.png")
'''


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — 3-Layer Triangle Fraud Detection API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vision.py setup           First-time setup (install + write files)
  python vision.py start           Start server (foreground, Ctrl+C to stop)
  python vision.py start -d        Start server in background
  python vision.py stop            Stop background server
  python vision.py validate        Run validation suite (24 cases + charts)
  python vision.py demo            Interactive demo (prompts for image paths)
  python vision.py all             Full pipeline (setup + start + validate)
        """,
    )
    parser.add_argument("-v", "--version", action="version",
                        version=f"{APP_NAME} v{APP_VERSION}")

    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")

    p_setup = sub.add_parser("setup", help="Install deps + write modules")
    p_setup.add_argument("-y", "--yes", action="store_true",
                         help="Auto-confirm installs")
    p_setup.set_defaults(func=cmd_setup)

    p_start = sub.add_parser("start", help="Start server")
    p_start.add_argument("-d", "--daemon", action="store_true",
                         help="Run in background")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop background server")
    p_stop.set_defaults(func=cmd_stop)

    p_val = sub.add_parser("validate", help="Run validation suite")
    p_val.set_defaults(func=cmd_validate)

    p_demo = sub.add_parser("demo", help="Interactive upload demo")
    p_demo.set_defaults(func=cmd_demo)

    p_all = sub.add_parser("all", help="Full pipeline")
    p_all.add_argument("-y", "--yes", action="store_true",
                       help="Auto-confirm installs")
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args()

    if not args.cmd:
        print_banner()
        print(f"  {BOLD}Usage:{RESET}")
        print(f"    python vision.py setup       — install deps + write files")
        print(f"    python vision.py start       — start server (foreground)")
        print(f"    python vision.py start -d    — start server (background)")
        print(f"    python vision.py validate    — run validation suite")
        print(f"    python vision.py demo        — interactive upload demo")
        print(f"    python vision.py all         — full pipeline")
        print(f"    python vision.py stop        — stop background server")
        print(f"\n  {GREEN}First time?{RESET} Run: python vision.py setup")
        return 0

    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}Interrupted by user{RESET}")
        sys.exit(130)