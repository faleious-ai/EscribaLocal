// Painel de Logs em tempo real — auto-contido, carregado depois do app.js.
// Consome GET /api/logs/stream (SSE) com filtros locais, pausa e autoscroll.
(function () {
    const openBtn = document.getElementById("btn-open-logs-panel");
    const modal = document.getElementById("logs-modal");
    const closeBtn = document.getElementById("logs-modal-close");
    const linesContainer = document.getElementById("logs-lines");
    const kindSelect = document.getElementById("logs-kind");
    const levelSelect = document.getElementById("logs-level");
    const filterInput = document.getElementById("logs-filter");
    const pauseBtn = document.getElementById("logs-pause");
    const clearBtn = document.getElementById("logs-clear");
    const autoscrollCheck = document.getElementById("logs-autoscroll");
    const statusLabel = document.getElementById("logs-status");

    if (!openBtn || !modal) return;

    const MAX_LINES = 500;
    let eventSource = null;
    let paused = false;
    let pausedBuffer = [];

    function setStatus(text, isError) {
        if (!statusLabel) return;
        statusLabel.textContent = text;
        statusLabel.style.color = isError ? "var(--accent-danger)" : "var(--text-muted)";
    }

    function detectLevel(rawLine) {
        try {
            const parsed = JSON.parse(rawLine);
            if (parsed.level) return String(parsed.level).toUpperCase();
        } catch (e) { /* linha não-JSON (app log) */ }
        const match = rawLine.match(/\b(CRITICAL|ERROR|WARNING|INFO|DEBUG)\b/);
        return match ? match[1] : "INFO";
    }

    function passesFilters(rawLine) {
        const level = levelSelect ? levelSelect.value : "";
        if (level && detectLevel(rawLine) !== level) return false;
        const needle = filterInput ? filterInput.value.trim().toLowerCase() : "";
        if (needle && !rawLine.toLowerCase().includes(needle)) return false;
        return true;
    }

    function formatLine(rawLine) {
        try {
            const parsed = JSON.parse(rawLine);
            const timestamp = (parsed.timestamp || "").replace("T", " ").slice(0, 19);
            const extras = Object.entries(parsed)
                .filter(([key]) => !["timestamp", "level", "logger", "message", "event_type", "request_id"].includes(key))
                .map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : value}`)
                .join(" ");
            return `${timestamp} [${parsed.level || "?"}] ${parsed.event_type || parsed.message || ""} ${extras}`.trim();
        } catch (e) {
            return rawLine;
        }
    }

    function appendLine(rawLine) {
        if (!passesFilters(rawLine)) return;
        const div = document.createElement("div");
        const level = detectLevel(rawLine);
        div.className = `log-line log-${level.toLowerCase()}`;
        div.textContent = formatLine(rawLine);
        div.title = rawLine;
        linesContainer.appendChild(div);
        while (linesContainer.childNodes.length > MAX_LINES) {
            linesContainer.removeChild(linesContainer.firstChild);
        }
        if (!autoscrollCheck || autoscrollCheck.checked) {
            linesContainer.scrollTop = linesContainer.scrollHeight;
        }
    }

    function handleRawLine(rawLine) {
        if (paused) {
            pausedBuffer.push(rawLine);
            if (pausedBuffer.length > MAX_LINES) pausedBuffer.shift();
            setStatus(`Pausado (${pausedBuffer.length} linhas em espera)`);
            return;
        }
        appendLine(rawLine);
    }

    function connect() {
        disconnect();
        const kind = kindSelect ? kindSelect.value : "events";
        eventSource = new EventSource(`/api/logs/stream?kind=${encodeURIComponent(kind)}&tail_lines=100`);
        setStatus("Conectado — acompanhando em tempo real");
        eventSource.onmessage = (message) => {
            let payload;
            try { payload = JSON.parse(message.data); } catch (e) { return; }
            if (payload.type === "log_line") handleRawLine(payload.line);
        };
        eventSource.onerror = () => {
            setStatus("Conexão perdida; tentando reconectar...", true);
        };
    }

    function disconnect() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    openBtn.addEventListener("click", () => {
        modal.style.display = "flex";
        linesContainer.innerHTML = "";
        pausedBuffer = [];
        paused = false;
        if (pauseBtn) pauseBtn.textContent = "⏸ Pausar";
        connect();
    });
    closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
        disconnect();
    });
    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            modal.style.display = "none";
            disconnect();
        }
    });

    if (kindSelect) kindSelect.addEventListener("change", () => {
        linesContainer.innerHTML = "";
        connect();
    });
    if (pauseBtn) pauseBtn.addEventListener("click", () => {
        paused = !paused;
        pauseBtn.textContent = paused ? "▶ Retomar" : "⏸ Pausar";
        if (!paused) {
            pausedBuffer.forEach(appendLine);
            pausedBuffer = [];
            setStatus("Conectado — acompanhando em tempo real");
        }
    });
    if (clearBtn) clearBtn.addEventListener("click", () => {
        linesContainer.innerHTML = "";
    });
})();
