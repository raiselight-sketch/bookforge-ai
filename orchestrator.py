"""
오케스트레이터 — 멀티에이전트 평가 파이프라인
4개 AI가 챕터별로 독립 평가 → 교차 검토 → 개선 실행의 3라운드를 수행합니다.
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from agents import GeminiAgent, ChatGPTAgent, ClaudeAgent, OllamaAgent
from agents.base_agent import BaseAgent, EvaluationResult, ImprovementResult, CrossReviewResult
import config


@dataclass
class ChapterData:
    """한 챕터의 데이터"""
    index: int
    title: str
    content: str
    part: str = ""


@dataclass
class RoundResult:
    """한 라운드의 결과"""
    round_number: int
    evaluations: list = field(default_factory=list)
    cross_reviews: list = field(default_factory=list)
    improvements: list = field(default_factory=list)
    consensus: dict = field(default_factory=dict)
    duration_seconds: float = 0.0


@dataclass
class PipelineState:
    """전체 파이프라인 상태"""
    status: str = "idle"  # idle, running, paused, completed, error
    current_round: int = 0
    total_rounds: int = 3
    current_chapter: int = 0
    total_chapters: int = 0
    current_phase: str = ""  # evaluating, cross_reviewing, improving
    current_agent: str = ""
    progress_percent: float = 0.0
    chapters: list = field(default_factory=list)
    rounds: list = field(default_factory=list)
    agents_status: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def to_dict(self):
        return asdict(self)


# 콜백 타입
ProgressCallback = Optional[callable]


class Orchestrator:
    """멀티에이전트 오케스트레이터"""

    def __init__(self):
        self.agents: list[BaseAgent] = []
        self.state = PipelineState()
        self._progress_callbacks: list[callable] = []

    async def initialize(self):
        """에이전트들을 초기화하고 연결 상태 확인"""
        agent_classes = [
            ("gemini", GeminiAgent),
            ("chatgpt", ChatGPTAgent),
            ("claude", ClaudeAgent),
            ("ollama", OllamaAgent),
        ]

        for key, AgentClass in agent_classes:
            model_config = config.MODELS.get(key, {})
            if not model_config.get("enabled", False):
                self.state.agents_status[key] = {
                    "name": model_config.get("name", key),
                    "status": "disabled",
                    "reason": "API 키 미설정",
                }
                continue

            try:
                agent = AgentClass()
                connected = await agent.check_connection()
                if connected:
                    self.agents.append(agent)
                    self.state.agents_status[key] = {
                        "name": agent.name,
                        "status": "connected",
                        "model": agent.model_id,
                        "specialty": agent.specialty,
                    }
                else:
                    self.state.agents_status[key] = {
                        "name": model_config.get("name", key),
                        "status": "connection_failed",
                        "reason": "API 연결 실패",
                    }
            except Exception as e:
                self.state.agents_status[key] = {
                    "name": model_config.get("name", key),
                    "status": "error",
                    "reason": str(e),
                }

        return len(self.agents) > 0

    def add_progress_callback(self, callback: callable):
        """진행 상태 변경 시 호출될 콜백 등록"""
        self._progress_callbacks.append(callback)

    async def _notify_progress(self):
        """등록된 콜백들에 진행 상태 알림"""
        for cb in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(self.state.to_dict())
                else:
                    cb(self.state.to_dict())
            except Exception:
                pass

    def parse_manuscript(self, manuscript_text: str) -> list[ChapterData]:
        """마크다운 원고를 챕터 단위로 분할"""
        chapters = []
        lines = manuscript_text.split('\n')
        current_chapter = None
        current_content = []
        current_part = ""
        chapter_index = 0

        for line in lines:
            # 부(Part) 제목 감지
            if line.startswith('# ') and ('부.' in line or '부. ' in line):
                current_part = line.strip('# ').strip()
                continue

            # 장(Chapter) 제목 감지
            if line.startswith('# ') and ('장.' in line or '장. ' in line or '여는 글' in line or '닫는 글' in line):
                # 이전 챕터 저장
                if current_chapter is not None:
                    current_chapter.content = '\n'.join(current_content).strip()
                    if current_chapter.content:
                        chapters.append(current_chapter)

                chapter_index += 1
                title = line.strip('# ').strip()
                current_chapter = ChapterData(
                    index=chapter_index,
                    title=title,
                    content="",
                    part=current_part,
                )
                current_content = [line]
                continue

            # "여는 글" 또는 "닫는 글" 감지
            if line.startswith('# 여는 글') or line.startswith('# 닫는 글'):
                if current_chapter is not None:
                    current_chapter.content = '\n'.join(current_content).strip()
                    if current_chapter.content:
                        chapters.append(current_chapter)

                chapter_index += 1
                title = line.strip('# ').strip()
                current_chapter = ChapterData(
                    index=chapter_index,
                    title=title,
                    content="",
                    part="",
                )
                current_content = [line]
                continue

            if current_chapter is not None:
                current_content.append(line)

        # 마지막 챕터 저장
        if current_chapter is not None:
            current_chapter.content = '\n'.join(current_content).strip()
            if current_chapter.content:
                chapters.append(current_chapter)

        return chapters

    async def run_pipeline(
        self,
        manuscript_text: str,
        num_rounds: int = 3,
    ) -> PipelineState:
        """전체 평가 파이프라인 실행"""
        self.state = PipelineState(
            status="running",
            total_rounds=num_rounds,
            start_time=time.time(),
        )

        # 1. 원고 파싱
        chapters = self.parse_manuscript(manuscript_text)
        self.state.total_chapters = len(chapters)
        self.state.chapters = [
            {"index": ch.index, "title": ch.title, "part": ch.part}
            for ch in chapters
        ]
        await self._notify_progress()

        if not chapters:
            self.state.status = "error"
            self.state.errors.append("챕터를 파싱할 수 없습니다.")
            return self.state

        if not self.agents:
            self.state.status = "error"
            self.state.errors.append("사용 가능한 AI 에이전트가 없습니다.")
            return self.state

        try:
            for round_num in range(1, num_rounds + 1):
                self.state.current_round = round_num
                round_result = RoundResult(round_number=round_num)
                round_start = time.time()

                # ── 라운드 1~N: 독립 평가 ──
                self.state.current_phase = "evaluating"
                await self._notify_progress()

                for ch_idx, chapter in enumerate(chapters):
                    self.state.current_chapter = ch_idx + 1
                    self._update_progress()
                    await self._notify_progress()

                    # 모든 에이전트가 동시에 평가
                    eval_tasks = []
                    for agent in self.agents:
                        self.state.current_agent = agent.name
                        await self._notify_progress()
                        eval_tasks.append(
                            agent.evaluate(chapter.content, chapter.title)
                        )

                    results = await asyncio.gather(*eval_tasks, return_exceptions=True)

                    chapter_evals = []
                    for result in results:
                        if isinstance(result, Exception):
                            chapter_evals.append(
                                EvaluationResult(
                                    agent_name="unknown",
                                    error=str(result),
                                ).to_dict()
                            )
                        else:
                            chapter_evals.append(result.to_dict())

                    round_result.evaluations.append({
                        "chapter": chapter.title,
                        "chapter_index": chapter.index,
                        "evaluations": chapter_evals,
                    })

                # ── 교차 검토 (라운드 2 이상) ──
                if round_num >= 2 and len(self.agents) >= 2:
                    self.state.current_phase = "cross_reviewing"
                    await self._notify_progress()

                    for ch_idx, chapter in enumerate(chapters):
                        self.state.current_chapter = ch_idx + 1
                        self._update_progress()

                        prev_evals = round_result.evaluations[ch_idx]["evaluations"]

                        review_tasks = []
                        for agent in self.agents:
                            self.state.current_agent = agent.name
                            await self._notify_progress()
                            review_tasks.append(
                                agent.cross_review(chapter.content, prev_evals)
                            )

                        reviews = await asyncio.gather(*review_tasks, return_exceptions=True)

                        chapter_reviews = []
                        for review in reviews:
                            if isinstance(review, Exception):
                                chapter_reviews.append(
                                    CrossReviewResult(
                                        agent_name="unknown",
                                        error=str(review),
                                    ).to_dict()
                                )
                            else:
                                chapter_reviews.append(review.to_dict())

                        round_result.cross_reviews.append({
                            "chapter": chapter.title,
                            "reviews": chapter_reviews,
                        })

                # ── 개선 실행 (마지막 라운드) ──
                if round_num == num_rounds:
                    self.state.current_phase = "improving"
                    await self._notify_progress()

                    # 가장 좋은 성능의 에이전트로 개선 실행
                    improver = self.agents[0]  # 첫 번째 사용 가능한 에이전트

                    for ch_idx, chapter in enumerate(chapters):
                        self.state.current_chapter = ch_idx + 1
                        self.state.current_agent = improver.name
                        self._update_progress()
                        await self._notify_progress()

                        # 모든 평가에서 제안 사항 수집
                        all_suggestions = []
                        for eval_data in round_result.evaluations[ch_idx]["evaluations"]:
                            suggestions = eval_data.get("suggestions", [])
                            if isinstance(suggestions, list):
                                all_suggestions.extend(suggestions)

                        if all_suggestions:
                            improvement = await improver.improve(
                                chapter.content,
                                all_suggestions,
                                chapter.title,
                            )
                            round_result.improvements.append({
                                "chapter": chapter.title,
                                "improvement": improvement.to_dict(),
                            })

                round_result.duration_seconds = round(time.time() - round_start, 2)
                self.state.rounds.append(asdict(round_result))

            self.state.status = "completed"
            self.state.progress_percent = 100.0

        except Exception as e:
            self.state.status = "error"
            self.state.errors.append(str(e))

        self.state.end_time = time.time()
        await self._notify_progress()

        # 결과 저장
        await self._save_results()

        return self.state

    def _update_progress(self):
        """진행률 계산"""
        if self.state.total_chapters == 0 or self.state.total_rounds == 0:
            return

        phases_per_round = 3  # evaluate, cross_review, improve
        phase_map = {"evaluating": 0, "cross_reviewing": 1, "improving": 2}
        phase_idx = phase_map.get(self.state.current_phase, 0)

        total_steps = self.state.total_rounds * phases_per_round * self.state.total_chapters
        current_step = (
            (self.state.current_round - 1) * phases_per_round * self.state.total_chapters
            + phase_idx * self.state.total_chapters
            + self.state.current_chapter
        )
        self.state.progress_percent = round(
            min(current_step / total_steps * 100, 99.9), 1
        )

    async def _save_results(self):
        """결과를 JSON 파일로 저장"""
        output_path = config.OUTPUT_DIR / "evaluation_results.json"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
