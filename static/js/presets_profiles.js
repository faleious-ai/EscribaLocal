// Presets e Perfis — renderiza dentro de #presets-profiles-container na sidebar.
// Consome: GET /api/presets, POST /api/presets/suggest, POST /api/presets/{id}/apply,
// GET /api/profiles, POST /api/profiles/{slug}/apply, POST /api/profiles/{slug}/save-from-form,
// DELETE /api/profiles/{slug}. Usa window.applyParamsToForm / collectParamsFromForm do app.js.
(function () {
    const container = document.getElementById("presets-profiles-container");
    if (!container) return;

    let presetsCache = [];

    function toast(message, isError) {
        if (typeof showToast === "function") showToast(message, Boolean(isError));
    }

    async function fetchJSON(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = response.statusText;
            try { detail = (await response.json()).detail || detail; } catch (e) { /* sem corpo JSON */ }
            throw new Error(detail);
        }
        return response.json();
    }

    function slugifyName(name) {
        return name.trim().toLowerCase()
            .normalize("NFD").replace(/[̀-ͯ]/g, "")
            .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
    }

    function render() {
        container.innerHTML = `
            <div class="pp-block">
                <label class="pp-label">🎛 Preset por hardware</label>
                <div class="pp-row">
                    <select id="pp-preset-select" class="logs-control" style="flex:1"></select>
                    <button type="button" id="pp-apply-preset" class="model-btn model-btn-primary">Aplicar</button>
                </div>
                <p id="pp-preset-info" class="model-notes"></p>
                <p id="pp-suggestion" class="model-notes"></p>
            </div>
            <div class="pp-block">
                <label class="pp-label">👤 Perfis salvos</label>
                <div class="pp-row">
                    <select id="pp-profile-select" class="logs-control" style="flex:1"></select>
                    <button type="button" id="pp-apply-profile" class="model-btn model-btn-primary">Aplicar</button>
                    <button type="button" id="pp-delete-profile" class="model-btn model-btn-danger" title="Excluir o perfil selecionado">🗑</button>
                </div>
                <div class="pp-row">
                    <input type="text" id="pp-profile-name" class="logs-control" style="flex:1" placeholder="Nome para salvar a config atual..." />
                    <button type="button" id="pp-save-profile" class="model-btn">💾 Salvar</button>
                </div>
            </div>
            <button type="button" id="pp-open-advanced" class="model-btn pp-advanced-btn">🧪 Modo avançado (todos os parâmetros)</button>
        `;

        document.getElementById("pp-apply-preset").addEventListener("click", applySelectedPreset);
        document.getElementById("pp-preset-select").addEventListener("change", showPresetInfo);
        document.getElementById("pp-apply-profile").addEventListener("click", applySelectedProfile);
        document.getElementById("pp-delete-profile").addEventListener("click", deleteSelectedProfile);
        document.getElementById("pp-save-profile").addEventListener("click", saveCurrentAsProfile);
        document.getElementById("pp-open-advanced").addEventListener("click", () => {
            if (window.openAdvancedParamsModal) window.openAdvancedParamsModal();
        });
    }

    const SUITABILITY_BADGES = { ok: "✓", tight: "⚠ apertado", not_recommended: "⛔ não recomendado" };

    async function loadPresets() {
        try {
            const data = await fetchJSON("/api/presets");
            presetsCache = data.presets || [];
            const select = document.getElementById("pp-preset-select");
            select.innerHTML = presetsCache.map((preset) =>
                `<option value="${preset.id}">${preset.label} ${SUITABILITY_BADGES[preset.suitability] || ""}</option>`
            ).join("");
            showPresetInfo();
        } catch (error) {
            toast(`Falha ao carregar presets: ${error.message}`, true);
        }
        try {
            const suggestion = await fetchJSON("/api/presets/suggest", { method: "POST" });
            const preset = presetsCache.find((p) => p.id === suggestion.preset_id);
            const label = preset ? preset.label : suggestion.preset_id;
            document.getElementById("pp-suggestion").innerHTML =
                `💡 Sugerido para este PC: <strong>${label}</strong> — ${suggestion.reason}`;
        } catch (error) { /* sugestão é opcional */ }
    }

    function showPresetInfo() {
        const select = document.getElementById("pp-preset-select");
        const preset = presetsCache.find((p) => p.id === select.value);
        const info = document.getElementById("pp-preset-info");
        if (!preset) { info.textContent = ""; return; }
        let text = preset.description;
        if (preset.suitability !== "ok") text += ` [${preset.suitability_reason}]`;
        info.textContent = text;
    }

    async function applySelectedPreset() {
        const select = document.getElementById("pp-preset-select");
        const preset = presetsCache.find((p) => p.id === select.value);
        if (!preset) return;
        if (preset.suitability === "not_recommended" &&
            !confirm(`O preset "${preset.label}" não é recomendado para este hardware:\n${preset.suitability_reason}\n\nAplicar mesmo assim?`)) {
            return;
        }
        try {
            const result = await fetchJSON(`/api/presets/${preset.id}/apply`, { method: "POST" });
            const applied = window.applyParamsToForm ? window.applyParamsToForm(result.form_params) : 0;
            toast(`Preset "${preset.label}" aplicado (${applied} parâmetros).`);
            logIfPossible("preset_applied_ui", { preset_id: preset.id });
        } catch (error) {
            toast(`Falha ao aplicar preset: ${error.message}`, true);
        }
    }

    async function loadProfiles() {
        try {
            const data = await fetchJSON("/api/profiles");
            const select = document.getElementById("pp-profile-select");
            const profiles = data.profiles || [];
            select.innerHTML = profiles.length
                ? profiles.map((p) => `<option value="${p.slug}">${p.name}</option>`).join("")
                : '<option value="">(nenhum perfil salvo)</option>';
        } catch (error) { /* lista vazia */ }
    }

    async function applySelectedProfile() {
        const slug = document.getElementById("pp-profile-select").value;
        if (!slug) { toast("Nenhum perfil selecionado.", true); return; }
        try {
            const settings = await fetchJSON(`/api/profiles/${slug}/apply`, { method: "POST" });
            if (window.applyParamsToForm && settings.form_params) {
                window.applyParamsToForm(settings.form_params);
            }
            toast(`Perfil "${slug}" aplicado.`);
        } catch (error) {
            toast(`Falha ao aplicar perfil: ${error.message}`, true);
        }
    }

    async function deleteSelectedProfile() {
        const select = document.getElementById("pp-profile-select");
        const slug = select.value;
        if (!slug) return;
        if (!confirm(`Excluir o perfil "${select.selectedOptions[0].textContent}"?`)) return;
        try {
            await fetchJSON(`/api/profiles/${slug}`, { method: "DELETE" });
            toast("Perfil excluído.");
            loadProfiles();
        } catch (error) {
            toast(`Falha ao excluir: ${error.message}`, true);
        }
    }

    async function saveCurrentAsProfile() {
        const nameInput = document.getElementById("pp-profile-name");
        const name = nameInput.value.trim();
        if (!name) { toast("Dê um nome ao perfil.", true); return; }
        const slug = slugifyName(name);
        if (!slug) { toast("Nome de perfil inválido.", true); return; }
        const engineParams = window.collectParamsFromForm ? window.collectParamsFromForm() : {};
        try {
            await fetchJSON(`/api/profiles/${slug}/save-from-form`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name, engine_params_form: engineParams }),
            });
            toast(`Perfil "${name}" salvo.`);
            nameInput.value = "";
            loadProfiles();
        } catch (error) {
            toast(`Falha ao salvar perfil: ${error.message}`, true);
        }
    }

    function logIfPossible(eventType, details) {
        if (typeof logClientEvent === "function") logClientEvent(eventType, { details: details });
    }

    document.addEventListener("DOMContentLoaded", () => {
        render();
        loadPresets();
        loadProfiles();
    });
})();
