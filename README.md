# 📚 BookForge AI — 멀티에이전트 출판 시스템

> 4개 AI 에이전트(Gemini · ChatGPT · Claude · Gemma4)가 서로 원고를 평가하고 개선하여,  
> 개인 출판사 수준의 완성도 높은 책을 만드는 범용 AI 출판 플랫폼

## ✨ 특징

- **4개 AI 동시 평가**: Gemini(구조·논리), ChatGPT(가독성·흥미), Claude(문체·깊이), Gemma4(교정·일관성)
- **3라운드 상호 평가**: 독립 평가 → 교차 검토 → 합의 기반 개선
- **실시간 대시보드**: WebSocket 기반 실시간 진행률 + 레이더 차트 시각화
- **로컬 AI 지원**: Ollama(Gemma4)로 API 키 없이도 평가 가능

## 🚀 시작하기

```bash
# 1. 가상환경 생성 및 의존성 설치
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. API 키 설정 (.env 파일)
cp .env.example .env
# .env 파일에 API 키 입력

# 3. 서버 실행
python main.py
# → http://localhost:8000
```

## 📁 구조

```
├── main.py              # FastAPI 앱
├── config.py            # 설정 (API 키, 모델, 프롬프트)
├── orchestrator.py      # 멀티에이전트 파이프라인
├── consensus.py         # 합의 엔진
├── agents/              # AI 에이전트 모듈
│   ├── base_agent.py
│   ├── gemini_agent.py
│   ├── chatgpt_agent.py
│   ├── claude_agent.py
│   └── ollama_agent.py
├── static/              # 웹 대시보드
│   ├── index.html
│   ├── index.css
│   └── app.js
├── manuscripts/         # 원고 저장
└── output/              # 평가 결과
```

## 📖 활용 예시

어떤 장르의 원고든 업로드하면 4개 AI가 자동으로 평가·교차검토·개선합니다.  
소설, 에세이, 논문, 기독교 서적 등 모든 분야에 사용 가능합니다.

## 🔑 필요한 API 키

| 서비스 | 환경변수 | 발급처 |
|--------|----------|--------|
| Gemini | `GOOGLE_API_KEY` | [AI Studio](https://aistudio.google.com/) |
| ChatGPT | `OPENAI_API_KEY` | [OpenAI](https://platform.openai.com/) |
| Claude | `ANTHROPIC_API_KEY` | [Anthropic](https://console.anthropic.com/) |
| Gemma4 | 불필요 (로컬) | [Ollama](https://ollama.com/) |

## 📜 라이선스

MIT License · 저작권 © 박광일 (빛의소리)
