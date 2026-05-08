"""
AI 멀티에이전트 출판 시스템 — FastAPI 메인 앱
"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import config
from orchestrator import Orchestrator
from consensus import ConsensusEngine

app = FastAPI(
    title="BookForge AI — 멀티에이전트 출판 시스템",
    description="4개 AI 에이전트가 원고를 상호 평가·교차검토·개선하여 출판 수준으로 완성하는 범용 AI 출판 플랫폼",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# 글로벌 오케스트레이터
orchestrator = Orchestrator()
consensus_engine = ConsensusEngine()

# WebSocket 연결 관리
active_connections: list[WebSocket] = []


async def broadcast_progress(state: dict):
    """모든 WebSocket 클라이언트에 진행 상태 전송"""
    for ws in active_connections[:]:
        try:
            await ws.send_json({"type": "progress", "data": state})
        except Exception:
            active_connections.remove(ws)


# ── API 엔드포인트 ──

@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 대시보드"""
    html_path = config.STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_status():
    """시스템 상태 확인"""
    return {
        "status": "ready",
        "agents": orchestrator.state.agents_status,
        "models": {
            k: {
                "name": v["name"],
                "enabled": v["enabled"],
                "specialty": v["specialty"],
                "color": v["color"],
                "icon": v["icon"],
            }
            for k, v in config.MODELS.items()
        },
    }


@app.post("/api/initialize")
async def initialize_agents():
    """에이전트 초기화"""
    success = await orchestrator.initialize()
    return {
        "success": success,
        "agents": orchestrator.state.agents_status,
        "active_count": len(orchestrator.agents),
    }


@app.post("/api/upload")
async def upload_manuscript(file: UploadFile = File(...)):
    """원고 파일 업로드"""
    content = await file.read()
    text = content.decode("utf-8")

    # 원고 저장
    save_path = config.MANUSCRIPTS_DIR / file.filename
    save_path.write_text(text, encoding="utf-8")

    # 챕터 파싱
    chapters = orchestrator.parse_manuscript(text)

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "chapters": [
            {"index": ch.index, "title": ch.title, "part": ch.part}
            for ch in chapters
        ],
        "total_chapters": len(chapters),
    }


@app.get("/api/manuscripts")
async def list_manuscripts():
    """저장된 원고 목록"""
    manuscripts = []
    for f in config.MANUSCRIPTS_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        chapters = orchestrator.parse_manuscript(text)
        manuscripts.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "total_chapters": len(chapters),
            "chapters": [
                {"index": ch.index, "title": ch.title, "part": ch.part}
                for ch in chapters
            ],
        })
    return {"manuscripts": manuscripts}


@app.post("/api/evaluate/{filename}")
async def start_evaluation(filename: str, rounds: int = 1):
    """평가 파이프라인 시작"""
    manuscript_path = config.MANUSCRIPTS_DIR / filename
    if not manuscript_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"파일을 찾을 수 없습니다: {filename}"},
        )

    text = manuscript_path.read_text(encoding="utf-8")

    # 에이전트 초기화
    if not orchestrator.agents:
        await orchestrator.initialize()

    if not orchestrator.agents:
        return JSONResponse(
            status_code=503,
            content={
                "error": "사용 가능한 AI 에이전트가 없습니다.",
                "agents": orchestrator.state.agents_status,
            },
        )

    # WebSocket 콜백 등록
    orchestrator.add_progress_callback(broadcast_progress)

    # 비동기로 평가 실행
    asyncio.create_task(orchestrator.run_pipeline(text, num_rounds=rounds))

    return {
        "status": "started",
        "filename": filename,
        "rounds": rounds,
        "active_agents": len(orchestrator.agents),
    }


@app.get("/api/progress")
async def get_progress():
    """현재 평가 진행 상태"""
    return orchestrator.state.to_dict()


@app.get("/api/results")
async def get_results():
    """평가 결과 조회"""
    result_path = config.OUTPUT_DIR / "evaluation_results.json"
    if not result_path.exists():
        return {"results": None, "message": "아직 평가 결과가 없습니다."}

    with open(result_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    return {"results": results}


@app.get("/api/results/download")
async def download_results():
    """평가 결과 JSON 다운로드"""
    result_path = config.OUTPUT_DIR / "evaluation_results.json"
    if not result_path.exists():
        return JSONResponse(
            status_code=404, content={"error": "결과 파일이 없습니다."}
        )
    return FileResponse(
        result_path, filename="evaluation_results.json", media_type="application/json"
    )


# ── WebSocket ──

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 진행 상태 WebSocket"""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # 초기 상태 전송
        await websocket.send_json({
            "type": "connected",
            "data": orchestrator.state.to_dict(),
        })
        while True:
            # 클라이언트 메시지 대기 (keep-alive)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ── 앱 시작 ──

@app.on_event("startup")
async def startup():
    """앱 시작 시 초기화"""
    config.MANUSCRIPTS_DIR.mkdir(exist_ok=True)
    config.OUTPUT_DIR.mkdir(exist_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
