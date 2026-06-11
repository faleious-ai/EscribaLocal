// Painel de Histórico e Retry - auto-contido
(function () {
    const openBtn = document.getElementById("btn-open-logs-panel"); // Usaremos logs como referência, mas criamos um botão próprio de histórico
    const modalHtml = `
        <div id="history-modal" class="modal-overlay" style="display: none;">
            <div class="modal-content models-modal-content">
                <div class="modal-header">
                    <h3>📊 Histórico de Tarefas & Reexecução</h3>
                    <button type="button" id="history-modal-close" class="modal-close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="logs-toolbar">
                        <select id="history-kind" class="logs-control">
                            <option value="">Todos os tipos</option>
                            <option value="transcribe_whisper">Whisper (ASR)</option>
                            <option value="transcribe_vibevoice">VibeVoice (ASR)</option>
                            <option value="model_download">Downloads</option>
                            <option value="pip_install">Instalações</option>
                        </select>
                        <select id="history-state" class="logs-control">
                            <option value="">Todos os estados</option>
                            <option value="completed">Concluído</option>
                            <option value="failed">Falhou</option>
                            <option value="cancelled">Cancelado</option>
                            <option value="running">Executando</option>
                            <option value="queued">Na Fila</option>
                        </select>
                        <button type="button" id="history-refresh" class="model-btn">🔄 Atualizar</button>
                    </div>
                    <div id="history-table-container" style="max-height: 400px; overflow-y: auto; margin-top: 15px;">
                        Carregando histórico...
                    </div>
                </div>
            </div>
        </div>
    `;

    // Injeta o modal de histórico no DOM
    const div = document.createElement("div");
    div.innerHTML = modalHtml;
    document.body.appendChild(div.firstElementChild);

    const historyModal = document.getElementById("history-modal");
    const closeBtn = document.getElementById("history-modal-close");
    const refreshBtn = document.getElementById("history-refresh");
    const kindSelect = document.getElementById("history-kind");
    const stateSelect = document.getElementById("history-state");
    const tableContainer = document.getElementById("history-table-container");

    // Adiciona botão na header do index.html para abrir o Histórico
    document.addEventListener("DOMContentLoaded", () => {
        const header = document.querySelector(".hardware-monitor");
        if (header) {
            const btn = document.createElement("button");
            btn.id = "btn-open-history-panel";
            btn.className = "btn-models-panel";
            btn.title = "Visualizar histórico de transcrições e tarefas";
            btn.textContent = "📊 Histórico";
            btn.style.marginLeft = "5px";
            btn.addEventListener("click", () => {
                historyModal.style.display = "flex";
                loadHistory();
            });
            // Injeta antes de logs
            const logsBtn = document.getElementById("btn-open-logs-panel");
            if (logsBtn) header.insertBefore(btn, logsBtn);
            else header.appendChild(btn);
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", () => { historyModal.style.display = "none"; });
    }
    if (historyModal) {
        historyModal.addEventListener("click", (e) => {
            if (e.target === historyModal) historyModal.style.display = "none";
        });
    }
    if (refreshBtn) {
        refreshBtn.addEventListener("click", loadHistory);
    }
    if (kindSelect) kindSelect.addEventListener("change", loadHistory);
    if (stateSelect) stateSelect.addEventListener("change", loadHistory);

    async function fetchJSON(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = response.statusText;
            try { detail = (await response.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        return response.json();
    }

    function toast(message, isError) {
        if (typeof showToast === "function") showToast(message, Boolean(isError));
    }

    function formatTime(seconds) {
        if (!seconds) return "--:--";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    const RETENTION_LABELS = {
        available: '<span style="color:var(--accent-cyan); font-weight:600;">✓ Disponível</span>',
        expired: '<span style="color:var(--text-muted);">Expirado</span>',
        retained_disabled: '<span style="color:var(--text-muted);">Desativado</span>',
    };

    const STATE_BADGES = {
        completed: '<span class="model-badge model-badge-ok">Concluído</span>',
        failed: '<span class="model-badge model-badge-busy" style="background:var(--accent-danger);">Falhou</span>',
        cancelled: '<span class="model-badge">Cancelado</span>',
        running: '<span class="model-badge model-badge-busy">Executando</span>',
        queued: '<span class="model-badge">Fila</span>',
    };

    async function loadHistory() {
        tableContainer.innerHTML = "Carregando histórico...";
        try {
            const kind = kindSelect.value;
            const state = stateSelect.value;
            let url = `/api/history?limit=50`;
            if (kind) url += `&kind=${kind}`;
            if (state) url += `&state=${state}`;

            const data = await fetchJSON(url);
            const history = data.history || [];

            if (!history.length) {
                tableContainer.innerHTML = '<p class="model-notes">Nenhum job encontrado no histórico.</p>';
                return;
            }

            const rows = history.map((job) => {
                const isASR = ["transcribe_whisper", "transcribe_vibevoice"].includes(job.kind);
                const canRetry = isASR && job.retention && job.retention.input_available;
                
                let retryBtn = "";
                if (canRetry) {
                    retryBtn = `<button class="model-btn model-btn-primary btn-retry" data-job-id="${job.job_id}">Refazer 🔄</button>`;
                } else if (isASR) {
                    retryBtn = `<span class="model-notes" style="font-size:11px;">Sem áudio</span>`;
                } else {
                    retryBtn = `<span class="model-notes" style="font-size:11px;">--</span>`;
                }

                const timeStr = job.created_at ? new Date(job.created_at * 1000).toLocaleString() : "--";
                const durStr = job.duration_ms ? `${(job.duration_ms / 1000).toFixed(1)}s` : "--";
                const retStr = isASR ? (RETENTION_LABELS[job.retention.input_retention_status] || "Expirado") : "--";

                let errorDetail = "";
                if (job.error) {
                    errorDetail = `<div class="job-error-detail" style="color:var(--accent-danger); font-size:11px; margin-top:4px; font-family:monospace; max-width:250px; overflow:hidden; text-overflow:ellipsis;">${job.error}</div>`;
                }

                return `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
                        <td style="padding:10px 5px;">
                            <strong style="font-size:12px;">${job.kind.replace("transcribe_", "")}</strong>
                            <div class="model-notes" style="font-size:10px;">ID: ${job.job_id.slice(0, 8)}</div>
                        </td>
                        <td style="padding:10px 5px; font-size:11px;">${timeStr}</td>
                        <td style="padding:10px 5px; font-size:11px;">${durStr}</td>
                        <td style="padding:10px 5px;">
                            ${STATE_BADGES[job.state] || job.state}
                            ${errorDetail}
                        </td>
                        <td style="padding:10px 5px; font-size:11px;">${retStr}</td>
                        <td style="padding:10px 5px;">${retryBtn}</td>
                    </tr>
                `;
            }).join("");

            tableContainer.innerHTML = `
                <table class="models-table" style="width:100%; border-collapse:collapse; text-align:left;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border-color);">
                            <th style="padding:10px 5px; font-size:12px;">Tarefa</th>
                            <th style="padding:10px 5px; font-size:12px;">Início</th>
                            <th style="padding:10px 5px; font-size:12px;">Duração</th>
                            <th style="padding:10px 5px; font-size:12px;">Estado</th>
                            <th style="padding:10px 5px; font-size:12px;">Áudio</th>
                            <th style="padding:10px 5px; font-size:12px;">Ações</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;

            // Atacha eventos de clique
            tableContainer.querySelectorAll(".btn-retry").forEach((button) => {
                button.addEventListener("click", () => {
                    const jobId = button.getAttribute("data-job-id");
                    triggerRetry(jobId);
                });
            });

        } catch (error) {
            tableContainer.innerHTML = `<p class="model-notes" style="color:var(--accent-danger);">Erro ao carregar histórico: ${error.message}</p>`;
        }
    }

    async function triggerRetry(jobId) {
        if (!confirm("Confirmar a reexecução desta transcrição?\n\nNota: Este retry preserva modelo, engine e parâmetros técnicos. Prompts/conteúdo sensível original não são armazenados e não serão reaplicados.")) return;
        
        try {
            const result = await fetchJSON(`/api/jobs/${jobId}/retry`, { method: "POST" });
            if (result.prompt_warning) {
                alert("Aviso: " + result.message);
            }
            toast("Tarefa de reexecução agendada!");
            historyModal.style.display = "none";
            
            // Tenta se acoplar a esta nova tarefa na UI principal se for possível
            if (window.showToast && result.job_id) {
                // Inicia streaming do novo job na UI se estiver disponível
                attachUIProgressToJob(result.job_id);
            }
        } catch (error) {
            toast(`Falha ao reexecutar: ${error.message}`, true);
        }
    }

    function attachUIProgressToJob(jobId) {
        // Exibe containers e zera barra de progresso no frontend principal
        const pContainer = document.getElementById("transcription-progress-container");
        const pStatus = document.getElementById("progress-status");
        const pFill = document.getElementById("progress-bar-fill");
        const pPercent = document.getElementById("progress-percentage");
        const stopBtn = document.getElementById("btn-stop-transcription");
        const workspace = document.getElementById("dual-workspace");
        const sList = document.getElementById("transcript-segments-list");

        if (pContainer) pContainer.style.display = "block";
        if (pStatus) pStatus.textContent = "Iniciando reexecução (retry)...";
        if (pFill) pFill.style.width = "0%";
        if (pPercent) pPercent.textContent = "0%";
        if (workspace) workspace.style.display = "grid";
        if (sList) sList.innerHTML = "";

        const eventSource = new EventSource(`/api/jobs/${jobId}/events`);
        
        eventSource.onmessage = (message) => {
            let event;
            try { event = JSON.parse(message.data); } catch (e) { return; }

            if (event.type === "status") {
                if (pStatus) pStatus.textContent = event.message;
            } else if (event.type === "progress") {
                if (pFill) pFill.style.width = `${event.progress}%`;
                if (pPercent) pPercent.textContent = `${event.progress.toFixed(0)}%`;
                if (pStatus) pStatus.textContent = `Processando: ${event.progress.toFixed(0)}%`;
                
                // Reaproveita função global do app.js
                if (typeof appendTranscriptSegment === "function") {
                    appendTranscriptSegment(event.segment);
                }
            } else if (event.type === "done") {
                if (pStatus) pStatus.textContent = "Reexecução concluída!";
                if (pFill) pFill.style.width = "100%";
                if (pPercent) pPercent.textContent = "100%";
                eventSource.close();
                if (typeof renderFinalTranscript === "function") {
                    renderFinalTranscript(event.full_transcript);
                }
                toast("Reexecução concluída com sucesso!");
            } else if (event.type === "error") {
                if (pStatus) pStatus.textContent = `Erro: ${event.message}`;
                eventSource.close();
                toast(`Reexecução falhou: ${event.message}`, true);
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
        };
    }
})();
