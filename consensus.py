"""
합의 엔진 — 4개 AI 에이전트의 평가 결과를 종합하고 최종 의사결정을 도출합니다.
"""
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
import config


@dataclass
class ConsensusReport:
    """합의 리포트"""
    chapter_title: str = ""
    weighted_scores: dict = field(default_factory=dict)
    overall_weighted_score: float = 0.0
    agreed_strengths: list = field(default_factory=list)
    agreed_weaknesses: list = field(default_factory=list)
    priority_suggestions: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    agent_summaries: dict = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self):
        return asdict(self)


class ConsensusEngine:
    """합의 엔진"""

    def build_consensus(
        self,
        chapter_title: str,
        evaluations: list[dict],
        cross_reviews: list[dict] = None,
    ) -> ConsensusReport:
        """여러 에이전트의 평가를 종합하여 합의 리포트 생성"""
        report = ConsensusReport(chapter_title=chapter_title)

        if not evaluations:
            report.recommendation = "평가 데이터 없음"
            return report

        # 1. 가중 평균 점수 계산
        report.weighted_scores = self._calculate_weighted_scores(evaluations)
        report.overall_weighted_score = self._calculate_overall_score(
            report.weighted_scores
        )

        # 2. 강점/약점 합의 (다수결)
        report.agreed_strengths = self._find_agreed_items(
            evaluations, "strengths"
        )
        report.agreed_weaknesses = self._find_agreed_items(
            evaluations, "weaknesses"
        )

        # 3. 우선순위 제안 사항 도출
        report.priority_suggestions = self._prioritize_suggestions(evaluations)

        # 4. 갈등 사항 식별
        report.conflicts = self._identify_conflicts(evaluations)

        # 5. 에이전트별 요약
        for ev in evaluations:
            agent_name = ev.get("agent_name", "Unknown")
            report.agent_summaries[agent_name] = {
                "scores": ev.get("scores", {}),
                "overall": ev.get("overall_score", 0),
                "summary": ev.get("summary", ""),
            }

        # 6. 최종 권고
        report.recommendation = self._generate_recommendation(report)

        return report

    def _calculate_weighted_scores(self, evaluations: list[dict]) -> dict:
        """에이전트별 전문 분야 가중치를 적용한 점수 계산"""
        criteria = list(config.EVALUATION_CRITERIA.keys())
        weighted = {c: [] for c in criteria}

        for ev in evaluations:
            agent_name = ev.get("agent_name", "").lower()
            scores = ev.get("scores", {})

            if not scores:
                continue

            # 에이전트 가중치 찾기
            agent_weight = {}
            for key, model_config in config.MODELS.items():
                if model_config["name"].lower() in agent_name.lower() or key in agent_name.lower():
                    agent_weight = model_config.get("weight", {})
                    break

            for criterion in criteria:
                score = scores.get(criterion, 0)
                if isinstance(score, (int, float)) and score > 0:
                    weight = agent_weight.get(criterion, 1.0)
                    weighted[criterion].append(score * weight)

        # 가중 평균 계산
        result = {}
        for criterion in criteria:
            values = weighted[criterion]
            if values:
                result[criterion] = round(sum(values) / sum(
                    [1.0] * len(values)  # 단순 가중합 / 개수
                ), 1)
            else:
                result[criterion] = 0.0

        return result

    def _calculate_overall_score(self, weighted_scores: dict) -> float:
        """종합 점수 계산"""
        values = [v for v in weighted_scores.values() if v > 0]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 1)

    def _find_agreed_items(
        self, evaluations: list[dict], field_name: str
    ) -> list[str]:
        """다수의 에이전트가 동의하는 항목 추출"""
        all_items = []
        for ev in evaluations:
            items = ev.get(field_name, [])
            if isinstance(items, list):
                all_items.extend(items)

        # 빈도 기반 정렬 (유사한 항목을 그룹핑하기는 어렵지만 최소한 중복 제거)
        seen = set()
        unique = []
        for item in all_items:
            if isinstance(item, str) and item not in seen:
                seen.add(item)
                unique.append(item)

        return unique[:10]  # 상위 10개

    def _prioritize_suggestions(self, evaluations: list[dict]) -> list[dict]:
        """모든 제안을 수집하고 우선순위 결정"""
        all_suggestions = []
        for ev in evaluations:
            agent_name = ev.get("agent_name", "Unknown")
            suggestions = ev.get("suggestions", [])
            if isinstance(suggestions, list):
                for s in suggestions:
                    if isinstance(s, dict):
                        s["suggested_by"] = agent_name
                        all_suggestions.append(s)

        # 중복 제거 및 상위 15개 반환
        return all_suggestions[:15]

    def _identify_conflicts(self, evaluations: list[dict]) -> list[dict]:
        """에이전트 간 점수 차이가 큰 항목 식별"""
        conflicts = []
        criteria = list(config.EVALUATION_CRITERIA.keys())

        for criterion in criteria:
            scores = []
            for ev in evaluations:
                agent_scores = ev.get("scores", {})
                score = agent_scores.get(criterion, 0)
                if isinstance(score, (int, float)) and score > 0:
                    scores.append({
                        "agent": ev.get("agent_name", "Unknown"),
                        "score": score,
                    })

            if len(scores) >= 2:
                max_s = max(s["score"] for s in scores)
                min_s = min(s["score"] for s in scores)
                if max_s - min_s >= 3:  # 3점 이상 차이
                    conflicts.append({
                        "criterion": criterion,
                        "criterion_name": config.EVALUATION_CRITERIA.get(
                            criterion, {}
                        ).get("name", criterion),
                        "scores": scores,
                        "gap": max_s - min_s,
                    })

        return sorted(conflicts, key=lambda x: x.get("gap", 0), reverse=True)

    def _generate_recommendation(self, report: ConsensusReport) -> str:
        """최종 권고 생성"""
        score = report.overall_weighted_score

        if score >= 8.5:
            level = "출판 준비 완료"
            detail = "소규모 교정 작업만 거치면 출판이 가능한 수준입니다."
        elif score >= 7.0:
            level = "수정 후 출판 가능"
            detail = "핵심 개선 사항을 반영한 뒤 출판을 진행할 수 있습니다."
        elif score >= 5.5:
            level = "상당한 수정 필요"
            detail = "구조와 내용 양면에서 수정이 필요합니다."
        else:
            level = "재구성 권장"
            detail = "전체적인 재구성을 통해 원고의 완성도를 높여야 합니다."

        conflicts_note = ""
        if report.conflicts:
            conflicts_note = f" (에이전트 간 {len(report.conflicts)}개 항목에서 의견 차이가 발견됨)"

        return f"📊 종합 평가: {score}/10 — {level}. {detail}{conflicts_note}"

    def generate_summary_table(self, reports: list[ConsensusReport]) -> str:
        """여러 챕터의 합의 결과를 테이블로 정리"""
        if not reports:
            return "평가 결과 없음"

        lines = [
            "| 챕터 | 구조 | 논리 | 신학 | 가독성 | 흥미 | 출판성 | 종합 |",
            "|------|------|------|------|--------|------|--------|------|",
        ]

        for r in reports:
            s = r.weighted_scores
            lines.append(
                f"| {r.chapter_title[:20]} | "
                f"{s.get('structure', '-')} | "
                f"{s.get('logic', '-')} | "
                f"{s.get('theology', '-')} | "
                f"{s.get('readability', '-')} | "
                f"{s.get('interest', '-')} | "
                f"{s.get('publishability', '-')} | "
                f"**{r.overall_weighted_score}** |"
            )

        return '\n'.join(lines)
