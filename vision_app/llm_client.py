import os, asyncio, json
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
