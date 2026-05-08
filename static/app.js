/* ═══════════════════════════════════════════
   BookForge AI — 멀티에이전트 출판 시스템
   프론트엔드 로직
   ═══════════════════════════════════════════ */

// ── 상태 관리 ──
const state = {
    agents: {},
    manuscripts: [],
    selectedManuscript: null,
    selectedMode: 'quick',
    ws: null,
    radarChart: null,
    isEvaluating: false,
};

const MODE_CONFIG = {
    quick:    { rounds: 1, label: '⚡ 빠른 평가', desc: '1라운드' },
    standard: { rounds: 2, label: '📝 중간 평가', desc: '2라운드 + 교차검토' },
    detailed: { rounds: 3, label: '🔬 자세한 평가', desc: '3라운드 + 개선' },
};

const PHASE_LABELS = {
    evaluating: '📝 독립 평가 중',
    cross_reviewing: '🔄 교차 검토 중',
    improving: '✨ 개선 실행 중',
};

const AGENT_COLORS = {
    gemini: '#4285F4',
    chatgpt: '#10A37F',
    claude: '#D97706',
    ollama: '#F97316',
};

// ── 초기화 ──
document.addEventListener('DOMContentLoaded', async () => {
    await loadStatus();
    await loadManuscripts();
    connectWebSocket();
});

// ── API 호출 ──
async function api(endpoint, options = {}) {
    try {
        const res = await fetch(`/api${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        return await res.json();
    } catch (err) {
        console.error(`API 오류 (${endpoint}):`, err);
        showToast(`API 오류: ${err.message}`, 'error');
        return null;
    }
}

// ── 시스템 상태 로드 ──
async function loadStatus() {
    const data = await api('/status');
    if (data) {
        state.agents = data.agents || {};
        renderAgentCards(data.models || {});
        renderAgentIndicators(data.models || {});
    }
}

// ── 에이전트 초기화 ──
async function initializeAgents() {
    const btn = document.getElementById('btn-init');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 연결 중...';

    const data = await api('/initialize', { method: 'POST' });

    if (data) {
        state.agents = data.agents || {};
        await loadStatus();
        showToast(`✅ ${data.active_count}개 에이전트 연결 완료`);
    }

    btn.disabled = false;
    btn.innerHTML = '🔌 에이전트 연결';
}

// ── 에이전트 카드 렌더링 ──
function renderAgentCards(models) {
    const container = document.getElementById('agent-cards');
    container.innerHTML = '';

    for (const [key, model] of Object.entries(models)) {
        const agentStatus = state.agents[key] || {};
        const status = agentStatus.status || 'disabled';
        const statusLabel = {
            connected: '✅ 연결됨',
            disabled: '⭕ 비활성',
            connection_failed: '❌ 연결 실패',
            error: '⚠️ 오류',
        }[status] || '⭕ 미확인';

        const card = document.createElement('div');
        card.className = 'agent-card';
        card.style.setProperty('--agent-color', model.color);
        card.innerHTML = `
            <div class="agent-header">
                <span class="agent-icon">${model.icon}</span>
                <span class="agent-name">${model.name}</span>
            </div>
            <div class="agent-specialty">${model.specialty}</div>
            <div class="agent-status ${status}">${statusLabel}</div>
            ${agentStatus.reason ? `<div style="margin-top:8px;font-size:0.75rem;color:var(--text-muted)">${agentStatus.reason}</div>` : ''}
        `;
        container.appendChild(card);
    }
}

// ── 에이전트 인디케이터 (헤더) ──
function renderAgentIndicators(models) {
    const container = document.getElementById('agent-indicators');
    container.innerHTML = '';

    for (const [key, model] of Object.entries(models)) {
        const agentStatus = state.agents[key] || {};
        const status = agentStatus.status || 'disabled';
        const dot = document.createElement('div');
        dot.className = `agent-dot ${status}`;
        dot.style.background = status === 'connected' ? model.color : '';
        dot.title = `${model.name}: ${status}`;
        container.appendChild(dot);
    }
}

// ── 원고 목록 로드 ──
async function loadManuscripts() {
    const data = await api('/manuscripts');
    if (data && data.manuscripts) {
        state.manuscripts = data.manuscripts;
        renderManuscriptList(data.manuscripts);
    }
}

function renderManuscriptList(manuscripts) {
    const container = document.getElementById('manuscript-list');
    container.innerHTML = '';

    if (manuscripts.length === 0) return;

    const header = document.createElement('div');
    header.style.cssText = 'display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;';

    const title = document.createElement('h3');
    title.style.cssText = 'font-size:0.9rem; color:var(--text-secondary); margin:0;';
    title.textContent = `📚 저장된 원고 (${manuscripts.length})`;

    const deleteAllBtn = document.createElement('button');
    deleteAllBtn.className = 'btn-delete-all';
    deleteAllBtn.textContent = '🗑️ 전체 삭제';
    deleteAllBtn.title = '모든 원고 삭제';
    deleteAllBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteAllManuscripts();
    });

    header.appendChild(title);
    header.appendChild(deleteAllBtn);
    container.appendChild(header);

    for (let i = 0; i < manuscripts.length; i++) {
        const ms = manuscripts[i];
        const item = document.createElement('div');
        item.className = 'manuscript-list-item';

        const info = document.createElement('div');
        info.className = 'ms-info';
        info.innerHTML = `
            <div class="ms-name">📄 ${ms.filename}</div>
            <div class="ms-meta">${ms.total_chapters}개 챕터 · ${(ms.size_bytes / 1024).toFixed(1)}KB</div>
        `;
        info.addEventListener('click', () => selectManuscript(ms));

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-delete-item';
        deleteBtn.textContent = '🗑️';
        deleteBtn.title = '삭제';
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            deleteManuscript(ms.filename);
        });

        item.appendChild(info);
        item.appendChild(deleteBtn);
        container.appendChild(item);
    }
}

// ── 원고 삭제 ──
async function deleteManuscript(filename) {
    if (!confirm(`"${filename}"을(를) 삭제하시겠습니까?`)) return;

    const data = await api(`/manuscripts/${filename}`, { method: 'DELETE' });
    if (data) {
        showToast(`🗑️ ${data.message}`);
        if (state.selectedManuscript === filename) {
            state.selectedManuscript = null;
            document.getElementById('manuscript-info').classList.add('hidden');
            document.getElementById('section-control').classList.add('hidden');
        }
        await loadManuscripts();
    }
}

async function deleteAllManuscripts() {
    if (!confirm('모든 원고를 삭제하시겠습니까?')) return;

    const data = await api('/manuscripts', { method: 'DELETE' });
    if (data) {
        showToast(`🗑️ ${data.message}`);
        state.selectedManuscript = null;
        document.getElementById('manuscript-info').classList.add('hidden');
        document.getElementById('section-control').classList.add('hidden');
        await loadManuscripts();
    }
}

// ── 원고 선택 ──
function selectManuscript(ms) {
    state.selectedManuscript = ms.filename;
    renderManuscriptInfo(ms);
    document.getElementById('section-control').classList.remove('hidden');
}

function renderManuscriptInfo(ms) {
    const container = document.getElementById('manuscript-info');
    container.classList.remove('hidden');

    let chaptersHtml = '';
    for (const ch of ms.chapters) {
        chaptersHtml += `
            <div class="chapter-item">
                <span class="chapter-num">${ch.index}</span>
                <span>${ch.title}</span>
                ${ch.part ? `<span class="chapter-part">${ch.part}</span>` : ''}
            </div>
        `;
    }

    container.innerHTML = `
        <h3>📖 ${ms.filename} <span style="font-weight:400;color:var(--text-muted)"> (${ms.total_chapters}개 챕터)</span></h3>
        <div class="chapter-list">${chaptersHtml}</div>
    `;
}

// ── 파일 업로드 ──
async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) await uploadFile(file);
}

function handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add('drag-over');
}

function handleDragLeave(event) {
    event.currentTarget.classList.remove('drag-over');
}

async function handleDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    const file = event.dataTransfer.files[0];
    if (file) await uploadFile(file);
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (data) {
        showToast(`✅ ${data.filename} 업로드 완료 (${data.total_chapters}개 챕터)`);
        await loadManuscripts();
        selectManuscript(data);
    }
}

// ── 평가 모드 선택 ──
function selectMode(card) {
    document.querySelectorAll('.eval-mode-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.selectedMode = card.dataset.mode;
}

// ── 평가 시작 ──
async function startEvaluation() {
    if (!state.selectedManuscript) {
        showToast('먼저 원고를 선택하세요.', 'warning');
        return;
    }

    const mode = MODE_CONFIG[state.selectedMode];
    const btn = document.getElementById('btn-evaluate');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> ${mode.label} 시작 중...`;
    state.isEvaluating = true;

    document.getElementById('section-progress').classList.remove('hidden');
    document.getElementById('progress-log').innerHTML = '';
    
    // 버튼 초기화
    const pauseBtn = document.getElementById('btn-pause');
    pauseBtn.innerHTML = '⏸️ 일시정지';
    pauseBtn.classList.replace('btn-primary', 'btn-outline');

    const data = await api(`/evaluate/${state.selectedManuscript}?rounds=${mode.rounds}&mode=${state.selectedMode}`, {
        method: 'POST',
    });

    if (data && data.status === 'started') {
        showToast(`🚀 ${data.active_agents}개 에이전트로 ${mode.label} 시작! (${mode.desc})`);
        addLogEntry(`${mode.label}: ${data.active_agents}개 에이전트, ${mode.desc}`);
    } else {
        btn.disabled = false;
        btn.innerHTML = '🚀 평가 시작';
        state.isEvaluating = false;
    }
}

// ── 일시정지 / 재개 ──
async function togglePause() {
    const pauseBtn = document.getElementById('btn-pause');
    const isPaused = pauseBtn.innerHTML.includes('재개');

    if (isPaused) {
        const data = await api('/evaluate/resume', { method: 'POST' });
        if (data) {
            pauseBtn.innerHTML = '⏸️ 일시정지';
            pauseBtn.classList.replace('btn-primary', 'btn-outline');
            showToast('▶️ 평가를 재개합니다.');
        }
    } else {
        const data = await api('/evaluate/pause', { method: 'POST' });
        if (data) {
            pauseBtn.innerHTML = '▶️ 평가 재개';
            pauseBtn.classList.replace('btn-outline', 'btn-primary');
            showToast('⏸️ 평가를 일시정지했습니다.');
        }
    }
}

// ── 평가 취소 ──
async function cancelEvaluation() {
    if (!confirm('평가를 취소하시겠습니까? 지금까지의 진행 내역은 사라집니다.')) return;

    const data = await api('/evaluate/cancel', { method: 'POST' });
    if (data) {
        showToast('🛑 평가가 취소되었습니다.');
        addLogEntry('평가 취소됨');
        
        // UI 정리
        state.isEvaluating = false;
        const btn = document.getElementById('btn-evaluate');
        btn.disabled = false;
        btn.innerHTML = '🚀 평가 시작';
        
        // 결과 섹션 숨기기
        document.getElementById('section-progress').classList.add('hidden');
    }
}

// ── WebSocket ──
function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket 연결됨');
    };

    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'progress') {
            updateProgress(msg.data);
        }
    };

    state.ws.onclose = () => {
        console.log('WebSocket 연결 끊김, 3초 후 재연결...');
        setTimeout(connectWebSocket, 3000);
    };

    state.ws.onerror = () => {};

    // Keep-alive
    setInterval(() => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send('ping');
        }
    }, 30000);
}

// ── 진행 상태 업데이트 ──
function updateProgress(data) {
    const bar = document.getElementById('progress-bar');
    const text = document.getElementById('progress-text');
    const round = document.getElementById('progress-round');
    const phase = document.getElementById('progress-phase');
    const chapter = document.getElementById('progress-chapter');
    const agent = document.getElementById('progress-agent');

    bar.style.width = `${data.progress_percent}%`;
    text.textContent = `${data.progress_percent}%`;
    round.textContent = `${data.current_round} / ${data.total_rounds}`;
    phase.textContent = PHASE_LABELS[data.current_phase] || data.current_phase || '-';
    chapter.textContent = data.current_chapter > 0 ? `${data.current_chapter} / ${data.total_chapters}` : '-';
    agent.textContent = data.current_agent || '-';

    if (data.current_agent && data.current_phase) {
        addLogEntry(`${PHASE_LABELS[data.current_phase] || data.current_phase} — ${data.current_agent} — 챕터 ${data.current_chapter}`);
    }

    if (data.status === 'completed') {
        state.isEvaluating = false;
        const btn = document.getElementById('btn-evaluate');
        btn.disabled = false;
        btn.innerHTML = '🚀 평가 시작';
        showToast('🎉 평가 완료!');
        addLogEntry('✅ 전체 평가 완료');
        loadResults();
    }

    if (data.status === 'error') {
        state.isEvaluating = false;
        const btn = document.getElementById('btn-evaluate');
        btn.disabled = false;
        btn.innerHTML = '🚀 평가 시작';
        showToast(`❌ 오류: ${data.errors.join(', ')}`, 'error');
    }
}

// ── 결과 로드 및 렌더링 ──
async function loadResults() {
    const data = await api('/results');
    if (data && data.results) {
        renderResults(data.results);
        document.getElementById('section-results').classList.remove('hidden');
    }
}

function renderResults(results) {
    if (!results.rounds || results.rounds.length === 0) return;

    const lastRound = results.rounds[results.rounds.length - 1];
    if (!lastRound.evaluations) return;

    // 점수 수집
    const allScores = { structure: [], logic: [], theology: [], readability: [], interest: [], publishability: [] };
    const agentData = {};

    for (const chapterEval of lastRound.evaluations) {
        for (const ev of chapterEval.evaluations) {
            if (ev.error || !ev.scores) continue;
            for (const [key, val] of Object.entries(ev.scores)) {
                if (allScores[key] !== undefined && typeof val === 'number') {
                    allScores[key].push(val);
                }
            }
            if (!agentData[ev.agent_name]) {
                agentData[ev.agent_name] = {
                    scores: { structure: [], logic: [], theology: [], readability: [], interest: [], publishability: [] },
                    strengths: [],
                    weaknesses: [],
                    summaries: [],
                };
            }
            for (const [key, val] of Object.entries(ev.scores)) {
                if (agentData[ev.agent_name].scores[key] && typeof val === 'number') {
                    agentData[ev.agent_name].scores[key].push(val);
                }
            }
            if (ev.strengths) agentData[ev.agent_name].strengths.push(...ev.strengths);
            if (ev.weaknesses) agentData[ev.agent_name].weaknesses.push(...ev.weaknesses);
            if (ev.summary) agentData[ev.agent_name].summaries.push(ev.summary);
        }
    }

    // 종합 점수 카드
    renderScoreCards(allScores);

    // 레이더 차트
    renderRadarChart(agentData);

    // AI 코멘트
    renderAIComments(agentData);

    // 챕터별 결과
    renderChapterResults(lastRound.evaluations);
}

function renderScoreCards(allScores) {
    const container = document.getElementById('score-cards');
    container.innerHTML = '';

    const labels = {
        structure: '구조', logic: '논리', theology: '신학',
        readability: '가독성', interest: '흥미', publishability: '출판성',
    };

    for (const [key, values] of Object.entries(allScores)) {
        const avg = values.length > 0 ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) : '-';
        const card = document.createElement('div');
        card.className = 'score-card';
        card.innerHTML = `
            <div class="score-label">${labels[key] || key}</div>
            <div class="score-value">${avg}</div>
            <div class="score-bar"><div class="score-bar-fill" style="width:${avg !== '-' ? avg * 10 : 0}%"></div></div>
        `;
        container.appendChild(card);
    }
}

function renderRadarChart(agentData) {
    const canvas = document.getElementById('radar-chart');
    const ctx = canvas.getContext('2d');

    if (state.radarChart) state.radarChart.destroy();

    const labels = ['구조', '논리', '신학', '가독성', '흥미', '출판성'];
    const keys = ['structure', 'logic', 'theology', 'readability', 'interest', 'publishability'];
    const colors = {
        'Gemini': { bg: 'rgba(66, 133, 244, 0.2)', border: '#4285F4' },
        'ChatGPT': { bg: 'rgba(16, 163, 127, 0.2)', border: '#10A37F' },
        'Claude': { bg: 'rgba(217, 119, 6, 0.2)', border: '#D97706' },
        'Gemma4 (Local)': { bg: 'rgba(249, 115, 22, 0.2)', border: '#F97316' },
    };

    const datasets = [];
    for (const [name, data] of Object.entries(agentData)) {
        const avgScores = keys.map(k => {
            const vals = data.scores[k] || [];
            return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
        });
        const color = colors[name] || { bg: 'rgba(139, 92, 246, 0.2)', border: '#8b5cf6' };
        datasets.push({
            label: name,
            data: avgScores,
            backgroundColor: color.bg,
            borderColor: color.border,
            borderWidth: 2,
            pointBackgroundColor: color.border,
        });
    }

    state.radarChart = new Chart(ctx, {
        type: 'radar',
        data: { labels, datasets },
        options: {
            responsive: true,
            scales: {
                r: {
                    min: 0,
                    max: 10,
                    ticks: { stepSize: 2, color: '#6b6780', backdropColor: 'transparent' },
                    grid: { color: 'rgba(139, 92, 246, 0.1)' },
                    angleLines: { color: 'rgba(139, 92, 246, 0.1)' },
                    pointLabels: { color: '#9b97b0', font: { size: 12, family: "'Noto Sans KR'" } },
                },
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9b97b0', font: { family: "'Noto Sans KR'" }, padding: 16 },
                },
            },
        },
    });
}

function renderAIComments(agentData) {
    const container = document.getElementById('ai-comments');
    container.innerHTML = '<h3 style="font-size:1rem;color:var(--text-secondary);margin-bottom:12px;">💬 AI 에이전트별 평가</h3>';

    const colorMap = {
        'Gemini': '#4285F4', 'ChatGPT': '#10A37F', 'Claude': '#D97706', 'Gemma4 (Local)': '#F97316',
    };

    for (const [name, data] of Object.entries(agentData)) {
        const strengths = [...new Set(data.strengths)].slice(0, 5);
        const weaknesses = [...new Set(data.weaknesses)].slice(0, 5);

        const comment = document.createElement('div');
        comment.className = 'ai-comment';
        comment.style.setProperty('--agent-color', colorMap[name] || '#8b5cf6');

        let summaryHtml = data.summaries.length > 0 ? `<p>${data.summaries[0]}</p>` : '';
        let strengthsHtml = strengths.map(s => `<span class="tag strength">✅ ${s}</span>`).join('');
        let weaknessesHtml = weaknesses.map(w => `<span class="tag weakness">⚠️ ${w}</span>`).join('');

        comment.innerHTML = `
            <div class="comment-header">
                <span>${name}</span>
            </div>
            <div class="comment-body">
                ${summaryHtml}
                ${strengthsHtml || weaknessesHtml ? `
                    <div class="tag-list" style="margin-top:10px;">${strengthsHtml}${weaknessesHtml}</div>
                ` : ''}
            </div>
        `;
        container.appendChild(comment);
    }
}

function renderChapterResults(evaluations) {
    const container = document.getElementById('chapter-results');
    container.innerHTML = '';

    for (const chapterEval of evaluations) {
        const card = document.createElement('div');
        card.className = 'chapter-result-card';

        // 평균 점수 계산
        let totalScore = 0;
        let scoreCount = 0;
        for (const ev of chapterEval.evaluations) {
            if (ev.overall_score && typeof ev.overall_score === 'number') {
                totalScore += ev.overall_score;
                scoreCount++;
            }
        }
        const avgScore = scoreCount > 0 ? (totalScore / scoreCount).toFixed(1) : '-';

        const bodyId = `ch-body-${chapterEval.chapter_index}`;
        card.innerHTML = `
            <div class="chapter-result-header" onclick="toggleChapter('${bodyId}')">
                <span class="ch-title">📖 ${chapterEval.chapter}</span>
                <span class="ch-score">${avgScore}/10</span>
            </div>
            <div class="chapter-result-body" id="${bodyId}">
                ${chapterEval.evaluations.map(ev => `
                    <div style="margin-bottom:12px;padding:10px;background:var(--bg-input);border-radius:var(--radius-sm);">
                        <div style="font-weight:600;margin-bottom:6px;">${ev.agent_name}</div>
                        ${ev.summary ? `<p style="font-size:0.85rem;color:var(--text-secondary);">${ev.summary}</p>` : ''}
                        ${ev.error ? `<p style="color:var(--accent-danger);font-size:0.85rem;">⚠️ ${ev.error}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
        container.appendChild(card);
    }
}

function toggleChapter(bodyId) {
    const body = document.getElementById(bodyId);
    if (body) body.classList.toggle('open');
}

// ── 유틸리티 ──
function addLogEntry(text) {
    const log = document.getElementById('progress-log');
    const time = new Date().toLocaleTimeString('ko-KR');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${time}</span>${text}`;
    log.prepend(entry);

    // 최대 50개 유지
    while (log.children.length > 50) {
        log.removeChild(log.lastChild);
    }
}

function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;

    if (type === 'error') toast.style.borderLeft = '3px solid var(--accent-danger)';
    else if (type === 'warning') toast.style.borderLeft = '3px solid var(--accent-warning)';
    else toast.style.borderLeft = '3px solid var(--accent-success)';

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
