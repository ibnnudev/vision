import io, base64, json
from typing import List, Dict, Optional, Tuple
from PIL import Image
import imagehash
from rapidfuzz import fuzz
from config import settings, MARKET_PRICE_DB, TIER1_PATTERNS
from database import get_all_originals
from llm_client import get_llm_client

def b64_to_image(b64: str) -> Image.Image:
    if "," in b64: b64 = b64.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")

def compute_hashes(img: Image.Image) -> Dict[str, list]:
    w, h = img.size
    variants = [img, img.crop((int(w*0.05), int(h*0.05), int(w*0.95), int(h*0.95)))]
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
            op_list = _parse_stored(orig["phash"])
            od_list = _parse_stored(orig["dhash"])
            ow_list = _parse_stored(orig["whash"])
            dp = min(hamming_hex(c, o) for c in hashes["phash"] for o in op_list)
            dd = min(hamming_hex(c, o) for c in hashes["dhash"] for o in od_list)
            dw = min(hamming_hex(c, o) for c in hashes["whash"] for o in ow_list)
            ed = min(dp, dd, dw)
            if per_image_best is None or ed < per_image_best["ensemble_dist"]:
                per_image_best = {"idx": idx, "matched_listing_id": orig["listing_id"],
                                   "matched_model": orig["model"], "pHash_dist": dp,
                                   "dHash_dist": dd, "wHash_dist": dw, "ensemble_dist": ed}
        image_results.append(per_image_best or {"idx": idx, "error": "no_match"})
        if per_image_best and (best_match is None or per_image_best["ensemble_dist"] < best_match["ensemble_dist"]):
            best_match = per_image_best
    if best_match and best_match["ensemble_dist"] <= settings.HAMMING_THRESHOLD:
        conf = max(0, (1 - best_match["ensemble_dist"]/64)) * 100
        return {"is_duplicate": True, "score": settings.W_IMAGE,
                "matched_listing_id": best_match["matched_listing_id"],
                "matched_model": best_match["matched_model"],
                "hamming_distance": best_match["ensemble_dist"],
                "pHash_dist": best_match["pHash_dist"], "dHash_dist": best_match["dHash_dist"],
                "wHash_dist": best_match["wHash_dist"],
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
