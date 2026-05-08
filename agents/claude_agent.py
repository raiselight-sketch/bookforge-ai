"""
ClaudeAgent — Anthropic Claude API 연동
전문 역할: 문학적 깊이, 문체 일관성, 표현력 평가
"""
from .base_agent import BaseAgent


class ClaudeAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Claude",
            model_id="claude-sonnet-4-20250514",
            specialty="문학적 깊이 · 문체 일관성 · 표현력",
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic
            from config import ANTHROPIC_API_KEY
            self._client = Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._client

    async def check_connection(self) -> bool:
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model_id,
                max_tokens=20,
                messages=[{"role": "user", "content": "연결 테스트. '성공'이라고만 답하세요."}],
            )
            return bool(response.content[0].text)
        except Exception:
            return False

    async def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int]:
        import asyncio
        client = self._get_client()

        def _sync_call():
            response = client.messages.create(
                model=self.model_id,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
            )
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return response.content[0].text, tokens

        return await asyncio.to_thread(_sync_call)
