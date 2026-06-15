// Painel de Modelos e Memória — auto-contido, carregado depois do app.js.
// Consome: GET /api/models, POST /api/models/download, DELETE /api/models/{id},
// GET /api/jobs/{id}/events (progresso via EventSource), POST /api/jobs/{id}/cancel,
// e (quando disponíveis, Lote 4) GET /api/models/loaded e POST /api/models/unload.
(function () {
    const openBtn = document.getElementById("btn-open-models-panel");
    const modal = document.getElementById("models-modal");
    const closeBtn = document.getElementById("models-modal-close");
    const tableContainer = document.getElementById("models-table-container");
    const memorySection = document.getElementById("models-memory-section");
    const loadedList = document.getElementById("models-loaded-list");

    if (!openBtn || !modal) return;

    // model_id -> { jobId, eventSource }
    const activeDownloads = new Map();
    const activeConversions = new Map();

    function toast(message, isError) {
        if (typeof showToast === "function") showToast(message, Boolean(isError));
        else console.log("[models]", message);
    }

    async function fetchJSON(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = response.statusText;
            try { detail = (await response.json()).detail || detail; } catch (e) { /* corpo não-JSON */ }
            const error = new Error(detail);
            error.status = response.status;
            throw error;
        }
        return response.json();
    }

    function formatMB(mb) {
        if (mb === null || mb === undefined) return "--";
        return mb >= 1000 ? (mb / 1000).toFixed(1) + " GB" : Math.round(mb) + " MB";
    }

    const ENGINE_LABELS = {
        whisper: "ASR · Whisper",
        vibevoice_asr: "ASR · VibeVoice",
        tts_1_5b: "TTS",
        tts_large: "TTS",
        tts_realtime: "TTS Realtime",
        tts_chatterbox: "TTS · Chatterbox",
    };

    // --- Renderização -------------------------------------------------------

    function render(models) {
        const rows = models.map((model) => renderRow(model)).join("");
        tableContainer.innerHTML = `
            <table class="models-table">
                <thead>
                    <tr><th>Modelo</th><th>Tipo</th><th>Tamanho</th><th>Status</th><th style="width:34%">Ações</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;

        tableContainer.querySelectorAll("[data-action]").forEach((button) => {
            button.addEventListener("click", () => {
                const modelId = button.getAttribute("data-model");
                const model = models.find((m) => m.id === modelId);
                const action = button.getAttribute("data-action");
                if (action === "download") startDownload(model);
                else if (action === "delete") deleteModel(model);
                else if (action === "cancel") cancelDownload(modelId);
                else if (action === "convert") startConversion(model);
                else if (action === "cancel-convert") cancelConversion(modelId);
            });
        });
    }

    function renderRow(model) {
        const downloading = activeDownloads.has(model.id);
        const converting = activeConversions.has(model.id);
        
        const sizeText = model.installed
            ? formatMB(model.size_on_disk_mb) + " no disco"
            : formatMB(model.approx_download_mb) + " (download)";

        let statusBadge;
        if (downloading) {
            statusBadge = '<span class="model-badge model-badge-busy">Baixando...</span>';
        } else if (converting) {
            statusBadge = '<span class="model-badge model-badge-busy">Convertendo...</span>';
        } else if (model.loaded) {
            statusBadge = '<span class="model-badge model-badge-loaded">Na memória</span>';
        } else if (model.status === "ready") {
            statusBadge = '<span class="model-badge model-badge-ok">Instalado</span>';
        } else if (model.status === "downloaded-raw") {
            statusBadge = '<span class="model-badge model-badge-warn">Apenas baixado</span>';
        } else if (model.status === "error") {
            const errTitle = model.conversion_error ? `title="${model.conversion_error.replace(/"/g, '&quot;')}"` : "";
            statusBadge = `<span class="model-badge model-badge-danger" ${errTitle}>Erro na conversão</span>`;
        } else if (model.partial) {
            statusBadge = '<span class="model-badge model-badge-warn">Parcial</span>';
        } else {
            statusBadge = '<span class="model-badge">Não instalado</span>';
        }

        const warn = model.recommended_for_6gb ? "" : '<span class="model-badge model-badge-warn" title="Acima da capacidade deste hardware">⚠ 6GB</span>';

        let actions;
        if (downloading) {
            actions = `
                <div class="model-dl-progress" id="model-dl-${model.id}">
                    <div class="model-dl-bar"><div class="model-dl-fill" style="width:0%"></div></div>
                    <span class="model-dl-text">aguardando dados...</span>
                </div>
                <button class="model-btn model-btn-danger" data-action="cancel" data-model="${model.id}">✖ Cancelar</button>`;
        } else if (converting) {
            actions = `
                <div class="model-dl-progress" id="model-convert-${model.id}">
                    <div class="model-dl-bar"><div class="model-dl-fill" style="width:0%"></div></div>
                    <span class="model-dl-text">aguardando conversão...</span>
                </div>
                <button class="model-btn model-btn-danger" data-action="cancel-convert" data-model="${model.id}">✖ Cancelar</button>`;
        } else if (model.status === "ready") {
            actions = `<button class="model-btn model-btn-danger" data-action="delete" data-model="${model.id}">🗑️ Remover do disco</button>`;
        } else if (model.status === "downloaded-raw" || model.status === "error") {
            actions = `
                <button class="model-btn model-btn-primary" data-action="convert" data-model="${model.id}">⚙️ Converter</button>
                <button class="model-btn model-btn-danger" style="margin-left: 4px;" data-action="delete" data-model="${model.id}">🗑️ Remover</button>`;
        } else if (model.installed && model.id !== "vibevoice-tts-1.5b") {
            actions = `<button class="model-btn model-btn-danger" data-action="delete" data-model="${model.id}">🗑️ Remover do disco</button>`;
        } else {
            actions = `<button class="model-btn model-btn-primary" data-action="download" data-model="${model.id}">⬇️ Baixar (${formatMB(model.approx_download_mb)})</button>`;
        }

        return `
            <tr>
                <td><strong>${model.display_name}</strong> ${warn}<div class="model-notes">${model.notes || ""}</div></td>
                <td>${ENGINE_LABELS[model.engine] || model.engine}</td>
                <td>${sizeText}</td>
                <td>${statusBadge}</td>
                <td>${actions}</td>
            </tr>`;
    }

    async function renderMemorySection() {
        try {
            const data = await fetchJSON("/api/models/loaded");
            memorySection.style.display = "block";
            const engines = data.engines || [];
            const loaded = engines.filter((engine) => engine.loaded);
            if (!loaded.length) {
                loadedList.innerHTML = '<p class="model-notes">Nenhuma engine carregada na memória agora.</p>';
                return;
            }
            loadedList.innerHTML = loaded.map((engine) => `
                <div class="model-loaded-chip">
                    <span>${engine.label}${engine.current_model ? " · " + engine.current_model : ""}
                        <small>(~${formatMB(engine.est_vram_mb)})</small></span>
                    <button class="model-btn model-btn-warn" data-unload="${engine.engine}">⏏ Descarregar</button>
                </div>`).join("") +
                `<button class="model-btn model-btn-warn" id="btn-unload-all" style="margin-top:8px;">⏏ Descarregar tudo</button>`;

            loadedList.querySelectorAll("[data-unload]").forEach((button) => {
                button.addEventListener("click", () => unload({ engine: button.getAttribute("data-unload") }));
            });
            const unloadAll = document.getElementById("btn-unload-all");
            if (unloadAll) unloadAll.addEventListener("click", () => unload({ all: true }));
        } catch (error) {
            // Rotas do Lote 4 indisponíveis: esconde a seção sem quebrar o painel.
            memorySection.style.display = "none";
        }
    }

    // --- Ações --------------------------------------------------------------

    async function refreshPanel() {
        try {
            const data = await fetchJSON("/api/models");
            await reattachRunningDownloads();
            render(data.models);
            await renderMemorySection();
        } catch (error) {
            tableContainer.innerHTML = `<p class="model-notes">Erro ao carregar o catálogo: ${error.message}</p>`;
        }
    }

    async function reattachRunningDownloads() {
        try {
            const data = await fetchJSON("/api/jobs?kind=model_download&state=running");
            (data.jobs || []).forEach((job) => {
                const modelId = job.params && job.params.model_id;
                if (modelId && !activeDownloads.has(modelId)) attachProgress(modelId, job.job_id);
            });
        } catch (error) { /* sem downloads ativos */ }

        try {
            const data = await fetchJSON("/api/jobs?kind=model_conversion&state=running");
            (data.jobs || []).forEach((job) => {
                const modelId = job.params && job.params.model_id;
                if (modelId && !activeConversions.has(modelId)) attachConversionProgress(modelId, job.job_id);
            });
        } catch (error) { /* sem conversões ativas */ }
    }

    async function startConversion(model) {
        if (!model) return;
        if (!confirm(`Iniciar a conversão do ${model.display_name}?\nEste processo é pesado e pode demorar alguns minutos.`)) return;
        try {
            const data = await fetchJSON(`/api/models/${model.id}/convert`, {
                method: "POST",
            });
            attachConversionProgress(model.id, data.job_id);
            toast(`Conversão de ${model.display_name} iniciada.`);
            refreshPanel();
        } catch (error) {
            toast(`Falha ao iniciar conversão: ${error.message}`, true);
        }
    }

    function attachConversionProgress(modelId, jobId) {
        const eventSource = new EventSource(`/api/jobs/${jobId}/events`);
        activeConversions.set(modelId, { jobId, eventSource });

        eventSource.onmessage = (message) => {
            let event;
            try { event = JSON.parse(message.data); } catch (e) { return; }

            if (event.type === "progress") {
                updateConversionProgressRow(modelId, event.message);
            } else if (event.type === "job_snapshot") {
                const state = event.job && event.job.state;
                if (state && state !== "running" && state !== "queued") finishConversion(modelId, state);
            } else if (event.type === "job_state") {
                if (["completed", "failed", "cancelled"].includes(event.state)) finishConversion(modelId, event.state, event.error);
            } else if (event.type === "error") {
                toast(`Erro na conversão: ${event.message}`, true);
            }
        };
        eventSource.onerror = () => {
            finishConversion(modelId, null);
        };
    }

    function updateConversionProgressRow(modelId, message) {
        const container = document.getElementById(`model-convert-${modelId}`);
        if (!container) return;
        const fill = container.querySelector(".model-dl-fill");
        const text = container.querySelector(".model-dl-text");
        if (fill) fill.style.width = "50%";
        if (text) text.textContent = message;
    }

    function finishConversion(modelId, state, error) {
        const entry = activeConversions.get(modelId);
        if (entry) {
            entry.eventSource.close();
            activeConversions.delete(modelId);
        }
        if (state === "completed") toast("Conversão concluída com sucesso!");
        else if (state === "failed") toast(`Conversão falhou: ${error || "verifique se os arquivos safetensors não estão corrompidos."}`, true);
        else if (state === "cancelled") toast("Conversão cancelada.", true);
        if (modal.style.display !== "none") refreshPanel();
    }

    async function cancelConversion(modelId) {
        const entry = activeConversions.get(modelId);
        if (!entry) return;
        try {
            await fetchJSON(`/api/jobs/${entry.jobId}/cancel`, { method: "POST" });
        } catch (error) {
            toast(`Falha ao cancelar conversão: ${error.message}`, true);
        }
    }

    async function startDownload(model) {
        if (!model) return;
        const sizeLabel = formatMB(model.approx_download_mb);
        const extra = model.recommended_for_6gb ? "" : "\n\nATENÇÃO: este modelo NÃO é recomendado para o seu hardware (6GB de VRAM).";
        if (!confirm(`Baixar ${model.display_name} (${sizeLabel}) de ${model.repo_id}?${extra}`)) return;
        try {
            const data = await fetchJSON("/api/models/download", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: model.id }),
            });
            attachProgress(model.id, data.job_id);
            toast(`Download de ${model.display_name} iniciado.`);
            refreshPanel();
        } catch (error) {
            toast(`Falha ao iniciar download: ${error.message}`, true);
        }
    }

    function attachProgress(modelId, jobId) {
        const eventSource = new EventSource(`/api/jobs/${jobId}/events`);
        activeDownloads.set(modelId, { jobId, eventSource });

        eventSource.onmessage = (message) => {
            let event;
            try { event = JSON.parse(message.data); } catch (e) { return; }

            if (event.type === "download_progress") {
                updateProgressRow(modelId, event);
            } else if (event.type === "job_snapshot") {
                const state = event.job && event.job.state;
                if (state && state !== "running" && state !== "queued") finishDownload(modelId, state);
            } else if (event.type === "job_state") {
                if (["completed", "failed", "cancelled"].includes(event.state)) finishDownload(modelId, event.state, event.error);
            } else if (event.type === "error") {
                toast(`Erro no download: ${event.message}`, true);
            }
        };
        eventSource.onerror = () => {
            // Conexão encerrada (job terminou ou servidor reiniciou): re-sincroniza.
            finishDownload(modelId, null);
        };
    }

    function updateProgressRow(modelId, event) {
        const container = document.getElementById(`model-dl-${modelId}`);
        if (!container) return;
        const fill = container.querySelector(".model-dl-fill");
        const text = container.querySelector(".model-dl-text");
        if (fill) fill.style.width = `${event.percent}%`;
        if (text) text.textContent = `${event.percent}% · ${event.current_mb}/${event.total_mb} MB · ${event.speed_mb} MB/s`;
    }

    function finishDownload(modelId, state, error) {
        const entry = activeDownloads.get(modelId);
        if (entry) {
            entry.eventSource.close();
            activeDownloads.delete(modelId);
        }
        if (state === "completed") toast("Download concluído com sucesso.");
        else if (state === "failed") toast(`Download falhou: ${error || "ver logs"}`, true);
        else if (state === "cancelled") toast("Download cancelado.", true);
        if (modal.style.display !== "none") refreshPanel();
    }

    async function cancelDownload(modelId) {
        const entry = activeDownloads.get(modelId);
        if (!entry) return;
        try {
            await fetchJSON(`/api/jobs/${entry.jobId}/cancel`, { method: "POST" });
        } catch (error) {
            toast(`Falha ao cancelar: ${error.message}`, true);
        }
    }

    async function deleteModel(model) {
        if (!model) return;
        if (!confirm(`Remover ${model.display_name} do disco (libera ${formatMB(model.size_on_disk_mb)})?\nO modelo precisará ser baixado de novo para usar.`)) return;
        try {
            const result = await fetchJSON(`/api/models/${model.id}`, { method: "DELETE" });
            toast(`Removido: ${formatMB(result.freed_mb)} liberados.`);
            refreshPanel();
        } catch (error) {
            toast(`Falha ao remover: ${error.message}`, true);
        }
    }

    async function unload(payload) {
        try {
            await fetchJSON("/api/models/unload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            toast("Memória liberada.");
            refreshPanel();
        } catch (error) {
            toast(`Falha ao descarregar: ${error.message}`, true);
        }
    }

    // --- Abertura/fechamento -------------------------------------------------

    openBtn.addEventListener("click", () => {
        modal.style.display = "flex";
        refreshPanel();
    });
    closeBtn.addEventListener("click", () => { modal.style.display = "none"; });
    modal.addEventListener("click", (event) => {
        if (event.target === modal) modal.style.display = "none";
    });
})();
