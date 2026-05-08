"""
OllamaAgent — 로컬 Ollama (Gemma4) 연동
전문 역할: 맞춤법 교정, 포맷 일관성, 최종 교정
"""
import aiohttp
from .base_agent import BaseAgent


class OllamaAgent(BaseAgent):
    def __init__(self):
        from config import OLLAMA_BASE_URL
        super().__init__(
            name="Gemma4 (Local)",
            model_id="gemma4:latest",
            specialty="맞춤법 교정 · 포맷 일관성 · 최종 교정",
        )
        self.base_url = OLLAMA_BASE_URL

    async def check_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return any("gemma4" in m for m in models)
            return False
        except Exception:
            return False

    async def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int]:
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 8192,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=600),  # 로컬 모델은 시간이 걸릴 수 있음
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"Ollama API 오류 ({resp.status}): {error_text}")

                data = await resp.json()
                content = data.get("message", {}).get("content", "")
                tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
                return content, tokens
