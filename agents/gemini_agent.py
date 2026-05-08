"""
GeminiAgent — Google Gemini API 연동
전문 역할: 구조 분석, 논리 흐름, 신학적 일관성 검증
"""
from .base_agent import BaseAgent


class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Gemini",
            model_id="gemini-2.5-flash",
            specialty="구조 분석 · 논리 흐름 · 신학적 일관성",
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            from config import GOOGLE_API_KEY
            self._client = genai.Client(api_key=GOOGLE_API_KEY)
        return self._client

    async def check_connection(self) -> bool:
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model_id,
            contents="간단한 연결 테스트입니다. '연결 성공'이라고만 답하세요."
        )
        return bool(response.text)

    async def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int]:
        import asyncio
        client = self._get_client()

        def _sync_call():
            response = client.models.generate_content(
                model=self.model_id,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.3,
                    "max_output_tokens": 8192,
                }
            )
            tokens = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                tokens = getattr(response.usage_metadata, 'total_token_count', 0)
            return response.text, tokens

        return await asyncio.to_thread(_sync_call)
