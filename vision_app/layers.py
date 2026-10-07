import io, base64, json
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
    # A 3x3 set of overlapping windows at several scales catches arbitrary
    # crops while keeping enough unaffected regions when an image is overlaid.
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
