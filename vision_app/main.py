import uuid, time, json, base64, os
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
                         json.dumps(hashes["whash"]))
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
                         json.dumps(hashes["whash"]))
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
