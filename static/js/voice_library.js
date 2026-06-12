// Biblioteca de Vozes do VibeVoice 1.5B — auto-contido, carregado após app.js.
// Renderiza em #voice-library-container (sidebar TTS) e no modal #voices-modal.
// Expõe window.collectTtsExtras(mode) consumido pelos envios do app.js.
(function () {
    const container = document.getElementById("voice-library-container");
    const modal = document.getElementById("voices-modal");
    const modalBody = document.getElementById("voices-modal-body");
    const modalClose = document.getElementById("voices-modal-close");
    if (!container || !modal) return;

    const RECOMMENDED_PHRASE = "Olá, esta é uma amostra da minha voz. Estou falando de " +
        "maneira clara, natural e tranquila para criar um novo perfil de voz.";
    const CONSENT_TEXT = "Confirmo que esta é minha voz ou que possuo autorização expressa " +
        "da pessoa cuja voz está sendo utilizada.";
    const GEN_STYLES = {
        estavel:    { label: "Estável",        cfg_scale: 2.0, n_diffusion_steps: 12 },
        natural:    { label: "Natural",        cfg_scale: 1.7, n_diffusion_steps: 10 },
        expressivo: { label: "Expressivo",     cfg_scale: 1.4, n_diffusion_steps: 16 },
        narrativo:  { label: "Narrativo",      cfg_scale: 1.8, n_diffusion_steps: 14 },
        personalizado: { label: "Personalizado", cfg_scale: null, n_diffusion_steps: null },
    };
    const STORAGE_KEY = "escriba_tts_voice_settings";

    let voicesCache = { presets: [], custom: [] };
    let settings = loadSettings();
    let recorder = null, recordedBlob = null, recordTimerId = null, meterRafId = null;

    function toast(message, isError) {
        if (typeof showToast === "function") showToast(message, Boolean(isError));
    }

    function loadSettings() {
        try {
            return Object.assign({
                voice_id: "", style: "natural", cfg_scale: 1.7, n_diffusion_steps: 10,
                max_frames: 0, seed: -1, failure_policy: "cpu", device: "auto",
                speaker_voices: {}, custom_styles: {},
            }, JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
        } catch (e) { return { voice_id: "", style: "natural", cfg_scale: 1.7,
            n_diffusion_steps: 10, max_frames: 0, seed: -1, failure_policy: "cpu",
            device: "auto", speaker_voices: {}, custom_styles: {} }; }
    }

    function saveSettings() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    }

    async function fetchJSON(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = response.statusText;
            try {
                const body = await response.json();
                detail = typeof body.detail === "string" ? body.detail
                    : (body.detail && body.detail.message) || JSON.stringify(body.detail || body);
            } catch (e) { /* sem corpo */ }
            const error = new Error(detail);
            error.status = response.status;
            throw error;
        }
        return response.json();
    }

    // ---- Extras enviados ao /api/tts/generate -------------------------------
    window.collectTtsExtras = function (mode) {
        const extras = {
            cfg_scale: settings.cfg_scale,
            n_diffusion_steps: settings.n_diffusion_steps,
            max_frames: settings.max_frames,
            seed: settings.seed,
            failure_policy: settings.failure_policy,
            device: settings.device,
        };
        if (settings.voice_id) extras.voice_id = settings.voice_id;
        if (mode === "dialog") {
            const map = {};
            for (const [speaker, vid] of Object.entries(settings.speaker_voices || {})) {
                if (vid) map[speaker] = vid;
            }
            if (Object.keys(map).length) extras.speaker_voices = JSON.stringify(map);
        }
        return extras;
    };

    // ---- Sidebar -------------------------------------------------------------
    function voiceOptionsHtml(selected, allowEmpty) {
        let html = allowEmpty ? `<option value="">(voz padrão da biblioteca)</option>` : "";
        html += `<optgroup label="Presets locais">` + voicesCache.presets.map((v) =>
            `<option value="${v.id}" ${v.id === selected ? "selected" : ""}>${v.name}</option>`
        ).join("") + `</optgroup>`;
        if (voicesCache.custom.length) {
            html += `<optgroup label="Vozes personalizadas">` + voicesCache.custom.map((v) =>
                `<option value="${v.id}" ${v.id === selected ? "selected" : ""}>${v.name}${v.is_default ? " ★" : ""}</option>`
            ).join("") + `</optgroup>`;
        }
        return html;
    }

    function renderSidebar() {
        const style = GEN_STYLES[settings.style] || GEN_STYLES.natural;
        container.innerHTML = `
            <div class="pp-block" style="margin-top:12px;">
                <label class="pp-label">🎙 Voz (VibeVoice 1.5B)</label>
                <div class="pp-row">
                    <select id="vl-voice" class="logs-control" style="flex:1">${voiceOptionsHtml(settings.voice_id, true)}</select>
                    <button type="button" id="vl-manage" class="model-btn">Gerenciar</button>
                </div>
                <label class="pp-label" style="margin-top:8px;">Estilo de geração</label>
                <div class="pp-row">
                    <select id="vl-style" class="logs-control" style="flex:1">
                        ${Object.entries(GEN_STYLES).map(([key, s]) =>
                            `<option value="${key}" ${key === settings.style ? "selected" : ""}>${s.label}</option>`).join("")}
                        ${Object.keys(settings.custom_styles || {}).map((name) =>
                            `<option value="custom:${name}" ${settings.style === "custom:" + name ? "selected" : ""}>★ ${name}</option>`).join("")}
                    </select>
                    <button type="button" id="vl-save-style" class="model-btn" title="Salvar os valores atuais como estilo nomeado">💾</button>
                </div>
                <details id="vl-advanced" style="margin-top:8px;">
                    <summary class="model-notes">Parâmetros reais do 1.5B (auditados)</summary>
                    <div class="vl-grid">
                        <label title="Adesão ao texto (CFG da difusão). 1.7 validado em PT-BR. <1.4 degrada a pronúncia; >2.5 soa tenso.">
                            CFG <input type="number" id="vl-cfg" class="logs-control adv-number" min="1.0" max="3.0" step="0.1" value="${settings.cfg_scale}"></label>
                        <label title="Passos de difusão por frame (4–40). Mais = mais fidelidade e mais tempo (linear).">
                            Passos <input type="number" id="vl-steps" class="logs-control adv-number" min="4" max="40" step="1" value="${settings.n_diffusion_steps}"></label>
                        <label title="Teto de frames (7.5/s). 0 = automático pelo texto; a geração termina antes, por fim de fala.">
                            Frames <input type="number" id="vl-frames" class="logs-control adv-number" min="0" max="4000" step="10" value="${settings.max_frames}"></label>
                        <label title="-1 = aleatória. Fixa reproduz a mesma tomada nesta máquina/dispositivo.">
                            Seed <input type="number" id="vl-seed" class="logs-control adv-number" min="-1" step="1" value="${settings.seed}"></label>
                        <label title="auto = GPU com retry em CPU; forçar troca recarrega o modelo automaticamente.">
                            Device <select id="vl-device" class="logs-control">
                                <option value="auto" ${settings.device === "auto" ? "selected" : ""}>auto</option>
                                <option value="cuda" ${settings.device === "cuda" ? "selected" : ""}>cuda</option>
                                <option value="cpu" ${settings.device === "cpu" ? "selected" : ""}>cpu</option>
                            </select></label>
                        <label title="fail = erro sem fallback; cpu = tenta CPU; sapi5 = permite voz do Windows como último recurso (sempre rotulada). Voz personalizada inválida é SEMPRE erro.">
                            Falha <select id="vl-policy" class="logs-control">
                                <option value="fail" ${settings.failure_policy === "fail" ? "selected" : ""}>falhar</option>
                                <option value="cpu" ${settings.failure_policy === "cpu" ? "selected" : ""}>tentar CPU</option>
                                <option value="sapi5" ${settings.failure_policy === "sapi5" ? "selected" : ""}>permitir SAPI5</option>
                            </select></label>
                    </div>
                </details>
                <details style="margin-top:8px;">
                    <summary class="model-notes">Vozes por speaker (diálogo)</summary>
                    <div id="vl-speakers">
                        ${[1, 2, 3, 4].map((n) => `
                            <div class="pp-row" style="align-items:center;">
                                <span class="model-notes" style="width:74px;">Speaker ${n}</span>
                                <select data-speaker="${n}" class="logs-control vl-speaker-voice" style="flex:1">
                                    ${voiceOptionsHtml((settings.speaker_voices || {})[n] || "", true)}
                                </select>
                            </div>`).join("")}
                    </div>
                </details>
            </div>`;

        container.querySelector("#vl-voice").addEventListener("change", (e) => {
            settings.voice_id = e.target.value; saveSettings();
        });
        container.querySelector("#vl-manage").addEventListener("click", openModal);
        container.querySelector("#vl-style").addEventListener("change", (e) => {
            settings.style = e.target.value;
            const custom = e.target.value.startsWith("custom:")
                ? settings.custom_styles[e.target.value.slice(7)] : GEN_STYLES[e.target.value];
            if (custom && custom.cfg_scale != null) {
                settings.cfg_scale = custom.cfg_scale;
                settings.n_diffusion_steps = custom.n_diffusion_steps;
            }
            saveSettings(); renderSidebar();
        });
        container.querySelector("#vl-save-style").addEventListener("click", () => {
            const name = prompt("Nome do estilo personalizado (CFG/passos atuais):");
            if (!name) return;
            settings.custom_styles[name.trim()] = {
                cfg_scale: settings.cfg_scale, n_diffusion_steps: settings.n_diffusion_steps,
            };
            settings.style = "custom:" + name.trim();
            saveSettings(); renderSidebar();
            toast(`Estilo "${name}" salvo.`);
        });
        const bind = (id, key, parser) => container.querySelector(id).addEventListener("change", (e) => {
            settings[key] = parser(e.target.value);
            settings.style = "personalizado";
            saveSettings();
        });
        bind("#vl-cfg", "cfg_scale", parseFloat);
        bind("#vl-steps", "n_diffusion_steps", (v) => parseInt(v, 10));
        bind("#vl-frames", "max_frames", (v) => parseInt(v, 10) || 0);
        bind("#vl-seed", "seed", (v) => parseInt(v, 10));
        container.querySelector("#vl-device").addEventListener("change", (e) => {
            settings.device = e.target.value; saveSettings();
        });
        container.querySelector("#vl-policy").addEventListener("change", (e) => {
            settings.failure_policy = e.target.value; saveSettings();
        });
        container.querySelectorAll(".vl-speaker-voice").forEach((select) => {
            select.addEventListener("change", () => {
                settings.speaker_voices = settings.speaker_voices || {};
                settings.speaker_voices[select.dataset.speaker] = select.value;
                saveSettings();
            });
        });
    }

    async function refreshVoices() {
        try {
            voicesCache = await fetchJSON("/api/tts/voices");
            renderSidebar();
            if (modal.style.display !== "none") renderModal();
        } catch (error) {
            toast(`Falha ao carregar vozes: ${error.message}`, true);
        }
    }

    // ---- Modal: lista + criação ---------------------------------------------
    function openModal() { modal.style.display = "flex"; renderModal(); }
    function closeModal() { modal.style.display = "none"; stopRecordingCleanup(); }

    function renderModal() {
        const customRows = voicesCache.custom.map((voice) => {
            const emb = (voice.model_embeddings || {}).vibevoice_1_5b || {};
            const validation = voice.validation
                ? `${voice.validation.status} ("${voice.validation.transcript}")` : "não testada";
            const quality = voice.analysis ? voice.analysis.quality_status : "?";
            return `
            <div class="adv-param" data-voice="${voice.id}">
                <div class="adv-param-head">
                    <strong>${voice.name}${voice.is_default ? " ★ padrão" : ""}</strong>
                    <span class="model-badge">${voice.source} · ${quality} · emb: ${emb.status || "?"}</span>
                </div>
                <div class="model-notes">
                    ${voice.duration_seconds}s · ${(voice.disk_bytes / 1e6).toFixed(1)}MB ·
                    criada ${String(voice.created_at || "").slice(0, 10)} ·
                    inteligibilidade: ${validation}
                </div>
                <div class="pp-row" style="flex-wrap:wrap; margin-top:6px;">
                    <button class="model-btn" data-act="ref">▶ Referência</button>
                    <button class="model-btn" data-act="preview">🔊 Prévia</button>
                    ${voice.has_previous_preview ? '<button class="model-btn" data-act="preview-prev">🔁 Prévia anterior (A/B)</button>' : ""}
                    <button class="model-btn" data-act="validate">✔ Testar PT-BR</button>
                    <button class="model-btn" data-act="rebuild">♻ Reprocessar</button>
                    <button class="model-btn" data-act="rename">✏ Renomear</button>
                    <button class="model-btn" data-act="default">★ Padrão</button>
                    <button class="model-btn" data-act="export">⬇ Exportar</button>
                    <button class="model-btn model-btn-danger" data-act="delete">🗑 Excluir</button>
                </div>
                <audio class="vl-audio" controls style="display:none; width:100%; margin-top:6px;"></audio>
            </div>`;
        }).join("") || '<p class="model-notes">Nenhuma voz personalizada ainda — crie a primeira abaixo.</p>';

        modalBody.innerHTML = `
            <h4 class="models-section-title">Presets locais</h4>
            ${voicesCache.presets.map((p) => `<div class="model-notes">• ${p.name} — ${p.notes}</div>`).join("")}
            <h4 class="models-section-title" style="margin-top:12px;">
                Vozes personalizadas (${(voicesCache.total_disk_bytes / 1e6 || 0).toFixed(1)}MB em disco)</h4>
            <div id="vl-custom-list">${customRows}</div>

            <h4 class="models-section-title" style="margin-top:14px;">+ Adicionar voz</h4>
            <p class="model-notes">Uma gravação limpa (5–15s), sem música, eco ou outras pessoas,
               produz o melhor resultado. Frase sugerida (fale à vontade, não é obrigatória):<br>
               <em>"${RECOMMENDED_PHRASE}"</em></p>
            <div class="pp-row"><input type="text" id="vl-new-name" class="logs-control" style="flex:1"
                 placeholder="Nome da nova voz..."></div>
            <label class="logs-autoscroll" style="margin:6px 0;">
                <input type="checkbox" id="vl-consent"> ${CONSENT_TEXT}</label>

            <div class="pp-row" style="margin-top:6px;">
                <input type="file" id="vl-file" accept=".wav,.mp3,.m4a,.flac,.ogg,.webm,audio/*" class="logs-control" style="flex:1">
                <button type="button" id="vl-upload" class="model-btn model-btn-primary">⬆ Enviar arquivo</button>
            </div>

            <div class="pp-block" style="margin-top:8px;">
                <div class="pp-row" style="align-items:center;">
                    <button type="button" id="vl-rec-start" class="model-btn model-btn-primary">⏺ Iniciar gravação</button>
                    <button type="button" id="vl-rec-stop" class="model-btn" disabled>⏹ Parar</button>
                    <span id="vl-rec-timer" class="model-notes">00:00</span>
                    <div class="model-dl-bar" style="flex:1;"><div id="vl-rec-meter" class="model-dl-fill" style="width:0%"></div></div>
                </div>
                <p id="vl-rec-warn" class="adv-risks" style="display:none;"></p>
                <audio id="vl-rec-audio" controls style="display:none; width:100%; margin-top:6px;"></audio>
                <div class="pp-row" style="margin-top:6px;">
                    <button type="button" id="vl-rec-save" class="model-btn model-btn-primary" disabled>💾 Criar voz com esta gravação</button>
                    <button type="button" id="vl-rec-again" class="model-btn" disabled>↺ Gravar novamente</button>
                </div>
            </div>
            <div class="pp-row" style="margin-top:8px;">
                <input type="file" id="vl-import-file" accept=".zip" class="logs-control" style="flex:1">
                <button type="button" id="vl-import" class="model-btn">⬆ Importar perfil (.zip)</button>
            </div>
            <p id="vl-analysis" class="model-notes"></p>`;

        bindModalActions();
    }

    function showAnalysis(analysis) {
        const target = document.getElementById("vl-analysis");
        if (!target || !analysis) return;
        target.innerHTML = `Análise: <strong>${analysis.quality_status}</strong> — ` +
            `${analysis.duration_seconds}s (fala ${analysis.speech_seconds}s, silêncio ${(analysis.silence_ratio * 100).toFixed(0)}%), ` +
            `RMS ${analysis.rms}, pico ${analysis.peak}` +
            (analysis.clipping_detected ? ", ⚠ clipping" : "") +
            (analysis.warnings && analysis.warnings.length ? `<br>⚠ ${analysis.warnings.join(" · ")}` : "");
    }

    function bindModalActions() {
        modalBody.querySelectorAll("[data-act]").forEach((button) => {
            button.addEventListener("click", () => handleVoiceAction(button));
        });
        document.getElementById("vl-upload").addEventListener("click", uploadVoice);
        document.getElementById("vl-rec-start").addEventListener("click", startRecording);
        document.getElementById("vl-rec-stop").addEventListener("click", stopRecording);
        document.getElementById("vl-rec-save").addEventListener("click", saveRecording);
        document.getElementById("vl-rec-again").addEventListener("click", resetRecording);
        document.getElementById("vl-import").addEventListener("click", importVoice);
    }

    async function handleVoiceAction(button) {
        const card = button.closest("[data-voice]");
        const voiceId = card.dataset.voice;
        const audio = card.querySelector(".vl-audio");
        const act = button.dataset.act;
        try {
            if (act === "ref") {
                audio.src = `/api/tts/voices/${voiceId}/reference?t=${Date.now()}`;
                audio.style.display = "block"; audio.play();
            } else if (act === "preview" || act === "preview-prev") {
                if (act === "preview") {
                    button.disabled = true; button.textContent = "Gerando...";
                    const info = await fetchJSON(`/api/tts/voices/${voiceId}/preview`, { method: "POST" });
                    toast(`Prévia: ${info.engine_label} (${info.duration_seconds}s)`);
                }
                audio.src = `/api/tts/voices/${voiceId}/preview?previous=${act === "preview-prev"}&t=${Date.now()}`;
                audio.style.display = "block"; audio.play();
                button.disabled = false; button.textContent = act === "preview" ? "🔊 Prévia" : "🔁 Prévia anterior (A/B)";
            } else if (act === "validate") {
                button.disabled = true; button.textContent = "Testando...";
                const result = await fetchJSON(`/api/tts/voices/${voiceId}/validate`, { method: "POST" });
                toast(`Inteligibilidade: ${result.validation.status} — "${result.validation.transcript}"`);
                refreshVoices();
            } else if (act === "rebuild") {
                button.disabled = true;
                await fetchJSON(`/api/tts/voices/${voiceId}/rebuild`, { method: "POST" });
                toast("Voz reprocessada (gere uma nova prévia para comparar A/B).");
                refreshVoices();
            } else if (act === "rename") {
                const name = prompt("Novo nome da voz:");
                if (!name) return;
                await fetchJSON(`/api/tts/voices/${voiceId}`, {
                    method: "PATCH", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name }),
                });
                refreshVoices();
            } else if (act === "default") {
                await fetchJSON(`/api/tts/voices/${voiceId}/set-default`, { method: "POST" });
                refreshVoices();
            } else if (act === "export") {
                window.open(`/api/tts/voices/${voiceId}/export`, "_blank");
            } else if (act === "delete") {
                if (!confirm("Excluir definitivamente esta voz, a prévia e os embeddings?")) return;
                await fetchJSON(`/api/tts/voices/${voiceId}`, { method: "DELETE" });
                toast("Voz excluída.");
                if (settings.voice_id === voiceId) { settings.voice_id = ""; saveSettings(); }
                refreshVoices();
            }
        } catch (error) {
            toast(error.message, true);
            button.disabled = false;
        }
    }

    function getNameAndConsent() {
        const name = document.getElementById("vl-new-name").value.trim();
        const consent = document.getElementById("vl-consent").checked;
        if (!name) { toast("Dê um nome à nova voz.", true); return null; }
        if (!consent) { toast("É obrigatório confirmar o consentimento sobre a voz.", true); return null; }
        return { name, consent };
    }

    async function createVoice(blob, filename, endpoint) {
        const info = getNameAndConsent();
        if (!info) return;
        const formData = new FormData();
        formData.append("file", blob, filename);
        formData.append("name", info.name);
        formData.append("consent_confirmed", "true");
        try {
            const result = await fetchJSON(endpoint, { method: "POST", body: formData });
            showAnalysis(result.analysis);
            toast(`Voz "${result.voice.name}" criada (${result.analysis.quality_status}).`);
            settings.voice_id = result.voice.id; saveSettings();
            refreshVoices();
        } catch (error) {
            toast(error.message, true);
        }
    }

    async function uploadVoice() {
        const input = document.getElementById("vl-file");
        if (!input.files.length) { toast("Escolha um arquivo de áudio.", true); return; }
        const file = input.files[0];
        await createVoice(file, file.name, "/api/tts/voices/upload");
    }

    async function importVoice() {
        const input = document.getElementById("vl-import-file");
        if (!input.files.length) { toast("Escolha um arquivo .zip exportado.", true); return; }
        const formData = new FormData();
        formData.append("file", input.files[0]);
        try {
            await fetchJSON("/api/tts/voices/import", { method: "POST", body: formData });
            toast("Perfil importado.");
            refreshVoices();
        } catch (error) { toast(error.message, true); }
    }

    // ---- Gravação ao vivo ----------------------------------------------------
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recorder = new MediaRecorder(stream);
            const chunks = [];
            recorder.ondataavailable = (e) => chunks.push(e.data);
            recorder.onstop = () => {
                recordedBlob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
                const audio = document.getElementById("vl-rec-audio");
                audio.src = URL.createObjectURL(recordedBlob);
                audio.style.display = "block";
                document.getElementById("vl-rec-save").disabled = false;
                document.getElementById("vl-rec-again").disabled = false;
                stream.getTracks().forEach((t) => t.stop());
            };
            recorder.start();

            // Cronômetro + medidor de volume (WebAudio) com avisos
            const started = Date.now();
            recordTimerId = setInterval(() => {
                const s = Math.floor((Date.now() - started) / 1000);
                document.getElementById("vl-rec-timer").textContent =
                    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
            }, 250);

            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 2048;
            ctx.createMediaStreamSource(stream).connect(analyser);
            const data = new Float32Array(analyser.fftSize);
            let lowCount = 0;
            const meter = () => {
                if (!recorder || recorder.state !== "recording") { ctx.close(); return; }
                analyser.getFloatTimeDomainData(data);
                let peak = 0, sum = 0;
                for (const v of data) { peak = Math.max(peak, Math.abs(v)); sum += v * v; }
                const rms = Math.sqrt(sum / data.length);
                document.getElementById("vl-rec-meter").style.width = `${Math.min(100, peak * 130)}%`;
                const warn = document.getElementById("vl-rec-warn");
                if (peak > 0.98) {
                    warn.textContent = "⚠ Clipping: o microfone está saturando — afaste-se ou reduza o ganho.";
                    warn.style.display = "block";
                } else if (rms < 0.01) {
                    if (++lowCount > 16) {
                        warn.textContent = "⚠ Volume muito baixo — aproxime-se do microfone.";
                        warn.style.display = "block";
                    }
                } else { lowCount = 0; warn.style.display = "none"; }
                meterRafId = requestAnimationFrame(meter);
            };
            meterRafId = requestAnimationFrame(meter);

            document.getElementById("vl-rec-start").disabled = true;
            document.getElementById("vl-rec-stop").disabled = false;
        } catch (error) {
            toast(`Sem acesso ao microfone: ${error.message}`, true);
        }
    }

    function stopRecording() {
        if (recorder && recorder.state === "recording") recorder.stop();
        stopRecordingCleanup(false);
    }

    function stopRecordingCleanup(reset = true) {
        if (recordTimerId) { clearInterval(recordTimerId); recordTimerId = null; }
        if (meterRafId) { cancelAnimationFrame(meterRafId); meterRafId = null; }
        const startBtn = document.getElementById("vl-rec-start");
        const stopBtn = document.getElementById("vl-rec-stop");
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        if (reset) { recorder = null; recordedBlob = null; }
    }

    function resetRecording() {
        recordedBlob = null;
        const audio = document.getElementById("vl-rec-audio");
        audio.style.display = "none"; audio.src = "";
        document.getElementById("vl-rec-save").disabled = true;
        document.getElementById("vl-rec-again").disabled = true;
        document.getElementById("vl-rec-timer").textContent = "00:00";
    }

    async function saveRecording() {
        if (!recordedBlob) { toast("Grave a voz primeiro.", true); return; }
        if (!confirm("Criar o perfil de voz com esta gravação?")) return;
        await createVoice(recordedBlob, "gravacao.webm", "/api/tts/voices/record");
    }

    // ---- Boot ----------------------------------------------------------------
    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
    document.addEventListener("DOMContentLoaded", refreshVoices);
})();
