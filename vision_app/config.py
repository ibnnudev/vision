import os

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
