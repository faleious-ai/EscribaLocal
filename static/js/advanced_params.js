// Modo Avançado — renderiza TODOS os parâmetros a partir de GET /api/parameters
// (fonte única: services/parameters_registry.py), com descrição, faixa, impacto
// e riscos. Aplica no formulário via window.applyParamsToForm.
(function () {
    const modal = document.getElementById("advanced-modal");
    const closeBtn = document.getElementById("advanced-modal-close");
    const body = document.getElementById("advanced-params-body");
    const applyBtn = document.getElementById("advanced-apply");
    const resetBtn = document.getElementById("advanced-reset");

    if (!modal || !body) return;

    const ENGINE_TITLES = {
        whisper: "📝 Whisper (transcrição)",
        vibevoice_asr: "🎙 VibeVoice ASR (transcrição com diarização)",
        tts: "🔊 TTS (geração de voz)",
    };
    const IMPACT_LABELS = {
        qualidade: "qualidade", velocidade: "velocidade",
        memoria: "memória", misto: "misto", conteudo: "conteúdo",
    };

    let registry = null;

    function toast(message, isError) {
        if (typeof showToast === "function") showToast(message, Boolean(isError));
    }

    function controlId(engine, name) {
        return `adv-${engine}-${name}`;
    }

    function buildControl(engine, spec, currentValue) {
        const id = controlId(engine, spec.name);
        const value = currentValue !== undefined && currentValue !== null && currentValue !== ""
            ? currentValue : (spec.default === null ? "" : spec.default);

        if (spec.type === "bool") {
            const checked = (value === true || value === "true") ? "checked" : "";
            return `<input type="checkbox" id="${id}" ${checked} />`;
        }
        if (spec.type === "enum") {
            const options = spec.choices.map((choice) =>
                `<option value="${choice}" ${String(choice) === String(value) ? "selected" : ""}>${choice}</option>`
            ).join("");
            return `<select id="${id}" class="logs-control">${options}</select>`;
        }
        if (spec.type === "int" || spec.type === "float") {
            const step = spec.type === "int" ? 1 : 0.05;
            return `<input type="number" id="${id}" class="logs-control adv-number" value="${value}"
                        min="${spec.min}" max="${spec.max}" step="${step}" />`;
        }
        return `<input type="text" id="${id}" class="logs-control" value="${value ?? ""}" />`;
    }

    function renderParam(engine, spec, currentValue) {
        const risks = spec.risks
            ? `<div class="adv-risks">⚠ ${spec.risks}</div>` : "";
        const range = (spec.min !== null && spec.max !== null)
            ? ` <small>(${spec.min}–${spec.max}, padrão ${spec.default})</small>`
            : (spec.default !== null ? ` <small>(padrão ${spec.default})</small>` : "");
        return `
            <div class="adv-param" title="${(spec.description || "").replace(/"/g, "&quot;")}">
                <div class="adv-param-head">
                    <label for="${controlId(engine, spec.name)}">${spec.label}${range}</label>
                    <span class="model-badge">${IMPACT_LABELS[spec.impact] || spec.impact}</span>
                </div>
                <div class="adv-param-control">${buildControl(engine, spec, currentValue)}</div>
                <div class="model-notes">${spec.description || ""}</div>
                ${risks}
            </div>`;
    }

    function renderAll(currentParams) {
        body.innerHTML = Object.entries(registry).map(([engine, specs]) => `
            <details class="adv-engine" ${engine === "whisper" ? "open" : ""}>
                <summary>${ENGINE_TITLES[engine] || engine}</summary>
                <div class="adv-engine-grid">
                    ${specs.map((spec) => renderParam(engine, spec, (currentParams[engine] || {})[spec.name])).join("")}
                </div>
            </details>`).join("");
    }

    function collectModalValues() {
        const out = {};
        for (const [engine, specs] of Object.entries(registry)) {
            out[engine] = {};
            for (const spec of specs) {
                const el = document.getElementById(controlId(engine, spec.name));
                if (!el) continue;
                if (spec.type === "bool") out[engine][spec.name] = el.checked;
                else if (el.value !== "") out[engine][spec.name] = el.value;
            }
        }
        return out;
    }

    async function open() {
        modal.style.display = "flex";
        if (!registry) {
            try {
                const data = await (await fetch("/api/parameters")).json();
                registry = data.engines;
            } catch (error) {
                body.innerHTML = `<p class="model-notes">Erro ao carregar parâmetros: ${error.message}</p>`;
                return;
            }
        }
        const current = window.collectParamsFromForm ? window.collectParamsFromForm() : {};
        renderAll(current);
    }

    function close() {
        modal.style.display = "none";
    }

    if (applyBtn) applyBtn.addEventListener("click", () => {
        const values = collectModalValues();
        const applied = window.applyParamsToForm ? window.applyParamsToForm(values) : 0;
        toast(`${applied} parâmetros aplicados ao formulário.`);
        close();
    });
    if (resetBtn) resetBtn.addEventListener("click", () => {
        const defaults = {};
        for (const [engine, specs] of Object.entries(registry || {})) {
            defaults[engine] = {};
            for (const spec of specs) defaults[engine][spec.name] = spec.default;
        }
        renderAll(defaults);
        toast("Controles restaurados aos padrões (clique Aplicar para efetivar).");
    });
    if (closeBtn) closeBtn.addEventListener("click", close);
    modal.addEventListener("click", (event) => {
        if (event.target === modal) close();
    });

    window.openAdvancedParamsModal = open;
})();
