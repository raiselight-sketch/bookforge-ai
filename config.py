"""
AI 멀티에이전트 출판 시스템 설정
환경변수에서 API 키를 로드하고 시스템 설정을 관리합니다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=True)

# ── 프로젝트 경로 ──
BASE_DIR = Path(__file__).parent
MANUSCRIPTS_DIR = BASE_DIR / "manuscripts"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# 디렉토리 자동 생성
MANUSCRIPTS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── API 키 ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ── AI 모델 설정 ──
MODELS = {
    "gemini": {
        "name": "Gemini",
        "model_id": "gemini-2.5-flash",
        "color": "#4285F4",
        "icon": "🔵",
        "specialty": "구조 분석 · 논리 흐름 · 신학적 일관성",
        "enabled": bool(GOOGLE_API_KEY),
        "weight": {
            "structure": 1.3,
            "logic": 1.3,
            "theology": 1.2,
            "readability": 0.9,
            "interest": 0.8,
            "publishability": 1.0,
        },
    },
    "chatgpt": {
        "name": "ChatGPT",
        "model_id": "gpt-4o",
        "color": "#10A37F",
        "icon": "🟢",
        "specialty": "가독성 · 독자 흥미 · 시장성 분석",
        "enabled": bool(OPENAI_API_KEY),
        "weight": {
            "structure": 0.9,
            "logic": 1.0,
            "theology": 0.8,
            "readability": 1.3,
            "interest": 1.3,
            "publishability": 1.2,
        },
    },
    "claude": {
        "name": "Claude",
        "model_id": "claude-4-sonnet-20250514",
        "color": "#D97706",
        "icon": "🟣",
        "specialty": "문학적 깊이 · 문체 일관성 · 표현력",
        "enabled": bool(ANTHROPIC_API_KEY),
        "weight": {
            "structure": 1.0,
            "logic": 1.1,
            "theology": 1.0,
            "readability": 1.2,
            "interest": 1.1,
            "publishability": 1.1,
        },
    },
    "ollama": {
        "name": "Gemma4 (Local)",
        "model_id": "gemma4:latest",
        "color": "#F97316",
        "icon": "🟠",
        "specialty": "맞춤법 교정 · 포맷 일관성 · 최종 교정",
        "enabled": True,  # 로컬이므로 항상 사용 가능
        "weight": {
            "structure": 0.8,
            "logic": 0.9,
            "theology": 0.9,
            "readability": 1.1,
            "interest": 0.8,
            "publishability": 1.0,
        },
    },
}

# ── 평가 기준 ──
EVALUATION_CRITERIA = {
    "structure": {"name": "구조", "description": "챕터 구성, 흐름, 전환의 자연스러움"},
    "logic": {"name": "논리", "description": "논증의 타당성, 근거의 적절성"},
    "theology": {"name": "신학", "description": "신학적 정확성, 성경 해석의 건전성"},
    "readability": {"name": "가독성", "description": "문장의 명료함, 읽기 쉬움"},
    "interest": {"name": "흥미", "description": "독자를 끌어들이는 힘, 스토리텔링"},
    "publishability": {"name": "출판성", "description": "상업 출판 기준 부합 여부"},
}

# ── 프롬프트 설정 ──
SYSTEM_PROMPT_EVALUATOR = """당신은 한국 기독교 출판 분야의 전문 편집자입니다.
다음 원고를 아래 기준으로 평가해주세요.

**평가 기준** (각 1~10점):
1. 구조 (structure): 챕터 구성, 흐름, 전환의 자연스러움
2. 논리 (logic): 논증의 타당성, 근거의 적절성  
3. 신학 (theology): 신학적 정확성, 성경 해석의 건전성
4. 가독성 (readability): 문장의 명료함, 읽기 쉬움
5. 흥미 (interest): 독자를 끌어들이는 힘, 스토리텔링
6. 출판성 (publishability): 상업 출판 기준 부합 여부

**반드시 아래 JSON 형식으로 응답하세요:**
```json
{
  "scores": {
    "structure": <점수>,
    "logic": <점수>,
    "theology": <점수>,
    "readability": <점수>,
    "interest": <점수>,
    "publishability": <점수>
  },
  "overall_score": <종합 점수>,
  "strengths": ["강점 1", "강점 2", ...],
  "weaknesses": ["약점 1", "약점 2", ...],
  "suggestions": [
    {
      "location": "해당 위치/문장",
      "original": "원문",
      "suggestion": "개선안",
      "reason": "이유"
    }
  ],
  "summary": "종합 평가 요약 (2~3문장)"
}
```
"""

SYSTEM_PROMPT_IMPROVER = """당신은 한국 기독교 출판 분야의 전문 편집자입니다.
아래 피드백을 바탕으로 원고를 개선해주세요.

**규칙:**
1. 저자의 고유한 문체와 신학적 관점을 반드시 유지하세요.
2. 은유와 비유(흙 벽돌, 구운 벽돌 등)를 보존하세요.
3. 성경 인용문은 정확히 유지하세요.
4. 맞춤법과 문법 오류를 수정하세요.
5. 문장의 가독성을 높이되 의미를 변경하지 마세요.
6. 개선한 부분에 <!-- EDITED: 이유 --> 주석을 달아주세요.

개선된 전체 원고를 마크다운 형식으로 출력하세요.
"""

SYSTEM_PROMPT_CROSS_REVIEW = """당신은 출판 편집 전문가입니다.
다른 AI 편집자들의 평가를 검토하고 의견을 제시해주세요.

**규칙:**
1. 각 평가의 타당성을 판단하세요.
2. 동의/반대 여부와 그 근거를 명확히 밝히세요.
3. 놓친 중요한 포인트가 있다면 추가하세요.

**반드시 아래 JSON 형식으로 응답하세요:**
```json
{
  "review_of": {
    "<agent_name>": {
      "agree": ["동의하는 포인트"],
      "disagree": ["반대하는 포인트와 이유"],
      "additions": ["추가 의견"]
    }
  },
  "final_priority_suggestions": [
    "최우선 개선 사항 1",
    "최우선 개선 사항 2"
  ]
}
```
"""

# ── 출판 설정 ──
BOOK_DEFAULTS = {
    "title": "",
    "subtitle": "",
    "author": "",
    "page_size": "A5",
    "font_body": "Noto Serif KR",
    "font_heading": "Noto Sans KR",
    "font_size": "11pt",
    "line_height": "1.8",
    "margin": "20mm 15mm 25mm 15mm",
}
