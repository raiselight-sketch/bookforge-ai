"""
ChatGPTAgent — OpenAI GPT-4o API 연동
전문 역할: 가독성 평가, 독자 흥미도, 시장성 분석
"""
from .base_agent import BaseAgent


class ChatGPTAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ChatGPT",
            model_id="gpt-4o",
            specialty="가독성 · 독자 흥미 · 시장성 분석",
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            from config import OPENAI_API_KEY
            self._client = OpenAI(api_key=OPENAI_API_KEY)
        return self._client

    async def check_connection(self) -> bool:
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": "연결 테스트. '성공'이라고만 답하세요."}],
                max_tokens=10,
            )
            return bool(response.choices[0].message.content)
        except Exception:
            return False

    async def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int]:
        import asyncio
        client = self._get_client()

        def _sync_call():
            response = client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            tokens = response.usage.total_tokens if response.usage else 0
            return response.choices[0].message.content, tokens

        return await asyncio.to_thread(_sync_call)
