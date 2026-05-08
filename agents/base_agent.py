"""
BaseAgent — 모든 AI 에이전트의 공통 인터페이스
각 에이전트(Gemini, ChatGPT, Claude, Ollama)가 이 클래스를 상속합니다.
"""
import json
import re
import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class EvaluationResult:
    """에이전트의 평가 결과를 담는 구조체"""
    agent_name: str
    scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ImprovementResult:
    """에이전트의 개선 결과를 담는 구조체"""
    agent_name: str
    improved_text: str = ""
    changes_made: list = field(default_factory=list)
    raw_response: str = ""
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class CrossReviewResult:
    """교차 검토 결과"""
    agent_name: str
    review_of: dict = field(default_factory=dict)
    final_priority_suggestions: list = field(default_factory=list)
    raw_response: str = ""
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class BaseAgent(ABC):
    """모든 AI 에이전트의 공통 인터페이스"""

    def __init__(self, name: str, model_id: str, specialty: str):
        self.name = name
        self.model_id = model_id
        self.specialty = specialty
        self._total_tokens = 0
        self._total_cost = 0.0

    @abstractmethod
    async def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int]:
        """
        AI API 호출 (서브클래스에서 구현)
        Returns: (response_text, tokens_used)
        """
        pass

    @abstractmethod
    async def check_connection(self) -> bool:
        """API 연결 상태 확인"""
        pass

    async def evaluate(self, chapter_text: str, chapter_title: str = "") -> EvaluationResult:
        """챕터를 평가하고 구조화된 결과를 반환"""
        from config import SYSTEM_PROMPT_EVALUATOR

        start_time = time.time()
        result = EvaluationResult(agent_name=self.name)

        user_prompt = f"## 평가 대상 챕터: {chapter_title}\n\n{chapter_text}"

        try:
            response, tokens = await self._call_api(SYSTEM_PROMPT_EVALUATOR, user_prompt)
            result.raw_response = response
            result.tokens_used = tokens
            self._total_tokens += tokens

            # JSON 파싱
            parsed = self._parse_json_response(response)
            if parsed:
                result.scores = parsed.get("scores", {})
                result.overall_score = parsed.get("overall_score", 0.0)
                result.strengths = parsed.get("strengths", [])
                result.weaknesses = parsed.get("weaknesses", [])
                result.suggestions = parsed.get("suggestions", [])
                result.summary = parsed.get("summary", "")
            else:
                result.error = "JSON 파싱 실패 — 원본 응답이 raw_response에 저장됨"

        except Exception as e:
            result.error = str(e)

        result.duration_seconds = round(time.time() - start_time, 2)
        return result

    async def improve(self, chapter_text: str, feedback: list[dict], chapter_title: str = "") -> ImprovementResult:
        """피드백을 반영하여 텍스트를 개선"""
        from config import SYSTEM_PROMPT_IMPROVER

        start_time = time.time()
        result = ImprovementResult(agent_name=self.name)

        feedback_text = "\n".join([
            f"- [{f.get('location', '전체')}] {f.get('suggestion', '')} (이유: {f.get('reason', '')})"
            for f in feedback
        ])

        user_prompt = f"""## 원고: {chapter_title}

### 개선 피드백:
{feedback_text}

### 원문:
{chapter_text}
"""

        try:
            response, tokens = await self._call_api(SYSTEM_PROMPT_IMPROVER, user_prompt)
            result.raw_response = response
            result.improved_text = self._extract_markdown(response)
            result.tokens_used = tokens
            self._total_tokens += tokens

            # 변경 사항 추출
            result.changes_made = self._extract_edit_comments(result.improved_text)

        except Exception as e:
            result.error = str(e)

        result.duration_seconds = round(time.time() - start_time, 2)
        return result

    async def cross_review(self, chapter_text: str, evaluations: list[dict]) -> CrossReviewResult:
        """다른 에이전트들의 평가를 교차 검토"""
        from config import SYSTEM_PROMPT_CROSS_REVIEW

        start_time = time.time()
        result = CrossReviewResult(agent_name=self.name)

        evals_text = ""
        for ev in evaluations:
            if ev.get("agent_name") == self.name:
                continue
            evals_text += f"\n### {ev['agent_name']}의 평가:\n"
            evals_text += f"- 점수: {ev.get('scores', {})}\n"
            evals_text += f"- 강점: {ev.get('strengths', [])}\n"
            evals_text += f"- 약점: {ev.get('weaknesses', [])}\n"
            evals_text += f"- 요약: {ev.get('summary', '')}\n"

        user_prompt = f"""## 원고 내용:
{chapter_text[:2000]}...

## 다른 편집자들의 평가:
{evals_text}
"""

        try:
            response, tokens = await self._call_api(SYSTEM_PROMPT_CROSS_REVIEW, user_prompt)
            result.raw_response = response
            result.tokens_used = tokens
            self._total_tokens += tokens

            parsed = self._parse_json_response(response)
            if parsed:
                result.review_of = parsed.get("review_of", {})
                result.final_priority_suggestions = parsed.get("final_priority_suggestions", [])
            else:
                result.error = "JSON 파싱 실패"

        except Exception as e:
            result.error = str(e)

        result.duration_seconds = round(time.time() - start_time, 2)
        return result

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """AI 응답에서 JSON 블록을 추출하고 파싱"""
        # 코드블록 안에 있는 JSON 추출
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 코드블록 없이 바로 JSON인 경우
        try:
            # { 로 시작하는 부분 찾기
            brace_start = response.index('{')
            brace_end = response.rindex('}') + 1
            return json.loads(response[brace_start:brace_end])
        except (ValueError, json.JSONDecodeError):
            pass

        return None

    def _extract_markdown(self, response: str) -> str:
        """응답에서 마크다운 텍스트를 추출"""
        # 마크다운 코드블록 안에 있는 경우
        md_match = re.search(r'```(?:markdown)?\s*\n(.*?)\n```', response, re.DOTALL)
        if md_match:
            return md_match.group(1)
        return response

    def _extract_edit_comments(self, text: str) -> list[str]:
        """<!-- EDITED: ... --> 주석을 추출"""
        return re.findall(r'<!-- EDITED:\s*(.*?)\s*-->', text)

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "model": self.model_id,
            "total_tokens": self._total_tokens,
        }
