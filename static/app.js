// Estado Global do Frontend
const state = {
    selectedFile: null,
    audioDuration: 0,
    startTime: null,
    timerInterval: null,
    transcriptionSegments: [],
    abortController: null,
    currentJobId: null,
    showTimestamps: true,
    showSpeakers: true,
    
    // Novas variáveis de gravação e live
    activeMode: "file", // "file", "record", "live"
    mediaRecorder: null,
    audioChunks: [],
    recordingTimerInterval: null,
    recordingSeconds: 0,
    isRecordingPaused: false,
    
    liveSocket: null,
    liveMediaRecorder: null,
    liveChunkTimer: null,
    liveStopping: false,
    lastLongformTtsModel: "tts_1_5b"
};


// Mapeamento de Elementos da Interface
const elements = {
    dropZone: document.getElementById("audio-drop-zone"),
    fileInput: document.getElementById("file-input"),
    activeFileBanner: document.getElementById("active-file-banner"),
    selectedFileName: document.getElementById("selected-file-name"),
    selectedFileSize: document.getElementById("selected-file-size"),
    btnCancelFile: document.getElementById("btn-cancel-file"),
    
    transcribeActionArea: document.getElementById("transcribe-action-area"),
    btnStartTranscription: document.getElementById("btn-start-transcription"),
    
    progressContainer: document.getElementById("transcription-progress-container"),
    progressStatus: document.getElementById("progress-status"),
    progressPercentage: document.getElementById("progress-percentage"),
    progressBarFill: document.getElementById("progress-bar-fill"),
    timeElapsed: document.getElementById("time-elapsed"),
    timeEta: document.getElementById("time-eta"),
    btnStopTranscription: document.getElementById("btn-stop-transcription"),
    asrModelStatus: document.getElementById("asr-model-status"),

    
    dualWorkspace: document.getElementById("dual-workspace"),
    workspaceAudioPlayer: document.getElementById("workspace-audio-player"),
    transcriptSegmentsList: document.getElementById("transcript-segments-list"),
    searchTranscript: document.getElementById("search-transcript"),
    
    btnCopyTranscript: document.getElementById("btn-copy-transcript"),
    btnDownloadTxt: document.getElementById("btn-download-txt"),
    
    toast: document.getElementById("toast-notification"),
    
    // Sliders & Controles
    inputEngine: document.getElementById("input-engine"),
    whisperOptionsContainer: document.getElementById("whisper-options-container"),
    vibevoiceOptionsContainer: document.getElementById("vibevoice-options-container"),
    vibevoicePrompt: document.getElementById("vibevoice-prompt"),
    vibevoiceDiarization: document.getElementById("vibevoice-diarization"),
    btnToggleTimestamps: document.getElementById("btn-toggle-timestamps"),
    btnToggleSpeakers: document.getElementById("btn-toggle-speakers"),
    
    
    inputModel: document.getElementById("input-model"),
    inputDevice: document.getElementById("input-device"),
    inputCompute: document.getElementById("input-compute"),
    inputBeam: document.getElementById("input-beam"),
    beamValue: document.getElementById("beam-value"),
    inputVad: document.getElementById("input-vad"),
    inputThreads: document.getElementById("input-threads"),
    threadsValue: document.getElementById("threads-value"),
    inputChunkSize: document.getElementById("input-chunk-size"),
    chunkValue: document.getElementById("chunk-value"),
    configChunkSize: document.getElementById("config-chunk-size"),
    
    // Novos controles avançados Whisper e VibeVoice
    whisperLanguage: document.getElementById("whisper-language"),
    whisperTemperature: document.getElementById("whisper-temperature"),
    whisperTempValue: document.getElementById("whisper-temp-value"),
    whisperPrompt: document.getElementById("whisper-prompt"),

    vibevoiceChunkSize: document.getElementById("vibevoice-chunk-size"),
    vibevoiceChunkValue: document.getElementById("vibevoice-chunk-value"),
    vibevoiceTemperature: document.getElementById("vibevoice-temperature"),
    vibevoiceTempValue: document.getElementById("vibevoice-temp-value"),
    vibevoiceRepetitionPenalty: document.getElementById("vibevoice-repetition-penalty"),
    vibevoiceRepValue: document.getElementById("vibevoice-rep-value"),
    vibevoiceTopP: document.getElementById("vibevoice-top-p"),
    vibevoiceToppValue: document.getElementById("vibevoice-topp-value"),
    vibevoiceTopK: document.getElementById("vibevoice-top-k"),
    vibevoiceTopkValue: document.getElementById("vibevoice-topk-value"),
    vibevoiceNumBeams: document.getElementById("vibevoice-num-beams"),
    vibevoiceBeamsValue: document.getElementById("vibevoice-beams-value"),
    vibevoiceMaxNewTokens: document.getElementById("vibevoice-max-new-tokens"),
    vibevoiceTokensValue: document.getElementById("vibevoice-tokens-value"),
    
    // Elementos de Navegação Principal e TTS
    modeTabAsr: document.getElementById("mode-tab-asr"),
    modeTabTts: document.getElementById("mode-tab-tts"),
    asrConfigsSidebar: document.getElementById("asr-configs-sidebar"),
    ttsConfigsSidebar: document.getElementById("tts-configs-sidebar"),
    asrWorkspaceContainer: document.getElementById("asr-workspace-container"),
    ttsWorkspaceContainer: document.getElementById("tts-workspace-container"),
    
    inputTtsModel: document.getElementById("input-tts-model"),
    inputTtsSpeaker: document.getElementById("input-tts-speaker"),
    inputTtsTemp: document.getElementById("input-tts-temp"),
    ttsTempValue: document.getElementById("tts-temp-value"),
    inputTtsSpeed: document.getElementById("input-tts-speed"),
    ttsSpeedValue: document.getElementById("tts-speed-value"),
    inputTtsRepPenalty: document.getElementById("input-tts-rep-penalty"),
    ttsRepValue: document.getElementById("tts-rep-value"),
    
    ttsInputText: document.getElementById("tts-input-text"),
    btnGenerateTts: document.getElementById("btn-generate-tts"),
    ttsResultSingle: document.getElementById("tts-result-single"),
    ttsAudioPlayerSingle: document.getElementById("tts-audio-player-single"),
    btnDownloadTtsSingle: document.getElementById("btn-download-tts-single"),
    ttsEngineStatusSingle: document.getElementById("tts-engine-status-single"),
    
    ttsInputDialog: document.getElementById("tts-input-dialog"),
    btnGenerateDialog: document.getElementById("btn-generate-dialog"),
    ttsResultDialog: document.getElementById("tts-result-dialog"),
    ttsAudioPlayerDialog: document.getElementById("tts-audio-player-dialog"),
    btnDownloadTtsDialog: document.getElementById("btn-download-tts-dialog"),
    ttsEngineStatusDialog: document.getElementById("tts-engine-status-dialog"),
    
    ttsChatMessages: document.getElementById("tts-chat-messages"),
    ttsChatInput: document.getElementById("tts-chat-input"),
    btnSendTtsChat: document.getElementById("btn-send-tts-chat"),
    ttsEngineStatusChat: document.getElementById("tts-engine-status-chat"),
    
    // Painéis de Microfone
    micRecordPanel: document.getElementById("mic-record-panel"),
    micRecordStatus: document.getElementById("mic-record-status"),
    recordingTimer: document.getElementById("recording-timer"),
    btnStartMicRecord: document.getElementById("btn-start-mic-record"),
    btnPauseMicRecord: document.getElementById("btn-pause-mic-record"),
    btnStopMicRecord: document.getElementById("btn-stop-mic-record"),
    
    micLivePanel: document.getElementById("mic-live-panel"),
    micLiveStatus: document.getElementById("mic-live-status"),
    btnStartMicLive: document.getElementById("btn-start-mic-live"),
    btnStopMicLive: document.getElementById("btn-stop-mic-live"),
    asrLiveModelStatus: document.getElementById("asr-live-model-status"),
    
    // Widgets de hardware
    cpuVal: document.querySelector("#cpu-stat .hw-value"),
    cpuBar: document.querySelector("#cpu-stat .hw-bar-inner"),
    ramVal: document.querySelector("#ram-stat .hw-value"),
    ramBar: document.querySelector("#ram-stat .hw-bar-inner"),
    gpuVal: document.querySelector("#gpu-stat .hw-value"),
    gpuBar: document.querySelector("#gpu-stat .hw-bar-inner")
};

// --- INICIALIZAÇÃO E EVENTOS DE CONFIGURAÇÃO ---
document.addEventListener("DOMContentLoaded", () => {
    logClientEvent("app_loaded", { severity: "info" });
    loadSettingsFromStorage();
    setupConfigEventListeners();
    setupDragAndDrop();
    setupFileSelection();
    setupActions();
    
    // Configura os modos de microfone
    setupInputModes();
    setupMicRecord();
    setupMicLive();
    
    // Inicia monitoramento de hardware do PC
    fetchSystemStatus();
    setInterval(fetchSystemStatus, 3000);
    
    // Inicializa o modal de informações detalhadas
    setupInfoModal();
});

// Mostra notificações (toast)
function showToast(message, isError = false) {
    elements.toast.textContent = message;
    elements.toast.style.borderColor = isError ? "var(--accent-danger)" : "var(--accent-cyan)";
    elements.toast.classList.add("show");
    if (isError) {
        logClientEvent("toast_error", { severity: "warning", message });
    }
    setTimeout(() => {
        elements.toast.classList.remove("show");
    }, 3000);
}

function getClientModelSnapshot() {
    return {
        active_mode: state.activeMode,
        asr_engine: elements.inputEngine ? elements.inputEngine.value : null,
        whisper_model: elements.inputModel ? elements.inputModel.value : null,
        whisper_device: elements.inputDevice ? elements.inputDevice.value : null,
        whisper_compute: elements.inputCompute ? elements.inputCompute.value : null,
        tts_model: elements.inputTtsModel ? elements.inputTtsModel.value : null
    };
}

function logClientEvent(eventType, fields = {}) {
    const payload = {
        event_type: eventType,
        severity: fields.severity || "info",
        message: fields.message || null,
        source: fields.source || "frontend",
        page: window.location.pathname,
        model: getClientModelSnapshot(),
        details: fields.details || {}
    };

    try {
        const body = JSON.stringify(payload);
        if (navigator.sendBeacon) {
            const blob = new Blob([body], { type: "application/json" });
            navigator.sendBeacon("/api/client-log", blob);
        } else {
            fetch("/api/client-log", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body,
                keepalive: true
            }).catch(() => {});
        }
    } catch (err) {
        console.warn("Falha ao registrar evento local:", err);
    }
}

window.addEventListener("error", (event) => {
    logClientEvent("window_error", {
        severity: "error",
        message: event.message,
        source: event.filename || "window",
        details: {
            line: event.lineno,
            column: event.colno
        }
    });
});

window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    logClientEvent("unhandled_rejection", {
        severity: "error",
        message: reason && reason.message ? reason.message : String(reason),
        source: "promise"
    });
});

async function readErrorMessage(response, fallbackMessage) {
    try {
        const data = await response.json();
        if (data && data.detail) {
            return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        }
    } catch (err) {
        console.warn("Não foi possível ler detalhe do erro:", err);
    }
    return fallbackMessage;
}

function getSelectedTtsModelLabel() {
    if (!elements.inputTtsModel) return "Modelo selecionado";
    const selected = elements.inputTtsModel.selectedOptions && elements.inputTtsModel.selectedOptions[0];
    return selected ? selected.textContent.trim() : elements.inputTtsModel.value;
}

function setModelStatus(element, caption, engineLabel, fallback = false) {
    if (!element) return;
    const labelNode = element.querySelector("span");
    const valueNode = element.querySelector("strong");
    if (labelNode) labelNode.textContent = caption;
    if (valueNode) valueNode.textContent = engineLabel || "Aguardando geração";
    element.dataset.fallback = fallback ? "true" : "false";
}

function setTtsEngineStatus(element, caption, engineLabel, fallback = false) {
    setModelStatus(element, caption, engineLabel, fallback);
}

function getSelectedAsrModelLabel() {
    if (elements.inputEngine.value === "vibevoice" && state.activeMode !== "live") {
        return "VibeVoice-ASR (microsoft/VibeVoice-ASR-HF)";
    }

    const selected = elements.inputModel.selectedOptions && elements.inputModel.selectedOptions[0];
    const modelLabel = selected ? selected.textContent.trim() : elements.inputModel.value;
    return `Whisper ${modelLabel} / ${elements.inputDevice.value} / ${elements.inputCompute.value}`;
}

function formatModelStatusLabel(data) {
    const parts = [data.engine_label || data.engine_key || "Modelo local"];
    if (data.device) parts.push(data.device);
    if (data.compute_type) parts.push(data.compute_type);
    return parts.join(" / ");
}

// Salva e carrega configurações locais (LocalStorage)
function saveSettingsToStorage() {
    const settings = {
        engine: elements.inputEngine.value,
        model: elements.inputModel.value,
        device: elements.inputDevice.value,
        compute: elements.inputCompute.value,
        beam: elements.inputBeam.value,
        vad: elements.inputVad.checked,
        threads: elements.inputThreads.value,
        chunkSize: elements.inputChunkSize.value,
        vibevoicePrompt: elements.vibevoicePrompt.value,
        vibevoiceDiarization: elements.vibevoiceDiarization.checked,
        
        // Novos campos
        whisperLanguage: elements.whisperLanguage.value,
        whisperTemperature: elements.whisperTemperature.value,
        whisperPrompt: elements.whisperPrompt.value,
        vibevoiceChunkSize: elements.vibevoiceChunkSize.value,
        vibevoiceTemperature: elements.vibevoiceTemperature.value,
        vibevoiceRepetitionPenalty: elements.vibevoiceRepetitionPenalty.value,
        vibevoiceTopP: elements.vibevoiceTopP.value,
        vibevoiceTopK: elements.vibevoiceTopK.value,
        vibevoiceNumBeams: elements.vibevoiceNumBeams.value,
        vibevoiceMaxNewTokens: elements.vibevoiceMaxNewTokens.value
    };
    localStorage.setItem("escriba_settings", JSON.stringify(settings));
}

function loadSettingsFromStorage() {
    const stored = localStorage.getItem("escriba_settings");
    if (stored) {
        try {
            const settings = JSON.parse(stored);
            elements.inputEngine.value = settings.engine || "whisper";
            elements.inputModel.value = settings.model || "large-v3-turbo";
            elements.inputDevice.value = settings.device || "cuda";
            elements.inputCompute.value = settings.compute || "float16";
            elements.inputBeam.value = settings.beam || 5;
            elements.inputVad.checked = settings.vad !== false;
            elements.inputThreads.value = settings.threads || 8;
            elements.inputChunkSize.value = settings.chunkSize || 5;
            elements.vibevoicePrompt.value = settings.vibevoicePrompt || "";
            elements.vibevoiceDiarization.checked = settings.vibevoiceDiarization !== false;
            
            // Novos campos Whisper
            elements.whisperLanguage.value = settings.whisperLanguage || "auto";
            elements.whisperTemperature.value = settings.whisperTemperature || "0.0";
            elements.whisperPrompt.value = settings.whisperPrompt || "";
            
            // Novos campos VibeVoice
            elements.vibevoiceChunkSize.value = settings.vibevoiceChunkSize || 60;
            elements.vibevoiceTemperature.value = settings.vibevoiceTemperature || "0.0";
            elements.vibevoiceRepetitionPenalty.value = settings.vibevoiceRepetitionPenalty || "1.1";
            elements.vibevoiceTopP.value = settings.vibevoiceTopP || "1.0";
            elements.vibevoiceTopK.value = settings.vibevoiceTopK || 50;
            elements.vibevoiceNumBeams.value = settings.vibevoiceNumBeams || 1;
            elements.vibevoiceMaxNewTokens.value = settings.vibevoiceMaxNewTokens || 2048;

            // Atualiza labels dos sliders
            elements.beamValue.textContent = elements.inputBeam.value;
            elements.threadsValue.textContent = elements.inputThreads.value;
            elements.chunkValue.textContent = elements.inputChunkSize.value;
            
            // Atualiza labels novos Whisper
            elements.whisperTempValue.textContent = parseFloat(elements.whisperTemperature.value).toFixed(1);
            
            // Atualiza labels novos VibeVoice
            elements.vibevoiceChunkValue.textContent = elements.vibevoiceChunkSize.value;
            elements.vibevoiceTempValue.textContent = parseFloat(elements.vibevoiceTemperature.value).toFixed(1);
            elements.vibevoiceRepValue.textContent = parseFloat(elements.vibevoiceRepetitionPenalty.value).toFixed(2);
            elements.vibevoiceToppValue.textContent = parseFloat(elements.vibevoiceTopP.value).toFixed(2);
            elements.vibevoiceTopkValue.textContent = elements.vibevoiceTopK.value;
            elements.vibevoiceBeamsValue.textContent = elements.vibevoiceNumBeams.value;
            elements.vibevoiceTokensValue.textContent = elements.vibevoiceMaxNewTokens.value;
            
            toggleEngineOptions(elements.inputEngine.value);
        } catch (e) {
            console.error("Erro ao carregar configurações salvas:", e);
        }
    } else {
        toggleEngineOptions("whisper");
    }
}

function toggleEngineOptions(engine) {
    if (engine === "vibevoice") {
        elements.whisperOptionsContainer.style.display = "none";
        elements.vibevoiceOptionsContainer.style.display = "block";
    } else {
        elements.whisperOptionsContainer.style.display = "block";
        elements.vibevoiceOptionsContainer.style.display = "none";
    }
}

function setupConfigEventListeners() {
    // Escuta mudanças nas opções e salva no LocalStorage
    [
        elements.inputEngine, elements.inputModel, elements.inputDevice, elements.inputCompute, 
        elements.inputVad, elements.vibevoiceDiarization, elements.whisperLanguage
    ].forEach(input => {
        input.addEventListener("change", (e) => {
            if (input === elements.inputEngine) {
                toggleEngineOptions(e.target.value);
            }
            saveSettingsToStorage();
        });
    });
    
    [elements.vibevoicePrompt, elements.whisperPrompt].forEach(textarea => {
        textarea.addEventListener("input", saveSettingsToStorage);
    });
    
    elements.inputBeam.addEventListener("input", (e) => {
        elements.beamValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    
    elements.inputThreads.addEventListener("input", (e) => {
        elements.threadsValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    
    elements.inputChunkSize.addEventListener("input", (e) => {
        elements.chunkValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    
    // Novos escutadores Whisper
    elements.whisperTemperature.addEventListener("input", (e) => {
        elements.whisperTempValue.textContent = parseFloat(e.target.value).toFixed(1);
        saveSettingsToStorage();
    });
    
    // Novos escutadores VibeVoice
    elements.vibevoiceChunkSize.addEventListener("input", (e) => {
        elements.vibevoiceChunkValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    elements.vibevoiceTemperature.addEventListener("input", (e) => {
        elements.vibevoiceTempValue.textContent = parseFloat(e.target.value).toFixed(1);
        saveSettingsToStorage();
    });
    elements.vibevoiceRepetitionPenalty.addEventListener("input", (e) => {
        elements.vibevoiceRepValue.textContent = parseFloat(e.target.value).toFixed(2);
        saveSettingsToStorage();
    });
    elements.vibevoiceTopP.addEventListener("input", (e) => {
        elements.vibevoiceToppValue.textContent = parseFloat(e.target.value).toFixed(2);
        saveSettingsToStorage();
    });
    elements.vibevoiceTopK.addEventListener("input", (e) => {
        elements.vibevoiceTopkValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    elements.vibevoiceNumBeams.addEventListener("input", (e) => {
        elements.vibevoiceBeamsValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
    elements.vibevoiceMaxNewTokens.addEventListener("input", (e) => {
        elements.vibevoiceTokensValue.textContent = e.target.value;
        saveSettingsToStorage();
    });
}

// --- APLICAÇÃO/COLETA DE PARÂMETROS (presets, perfis e modo avançado) ---
// Mapeia nome de campo da API -> elemento do formulário + evento que os
// listeners existentes escutam (disparar o evento atualiza spans e storage).
const FORM_FIELD_MAP = {
    whisper: {
        model: { key: "inputModel", event: "change" },
        device: { key: "inputDevice", event: "change" },
        compute_type: { key: "inputCompute", event: "change" },
        beam_size: { key: "inputBeam", event: "input" },
        language: { key: "whisperLanguage", event: "change" },
        vad_filter: { key: "inputVad", event: "change", checkbox: true },
        cpu_threads: { key: "inputThreads", event: "input" },
        whisper_prompt: { key: "whisperPrompt", event: "input" },
        whisper_temperature: { key: "whisperTemperature", event: "input" },
    },
    vibevoice_asr: {
        vibevoice_prompt: { key: "vibevoicePrompt", event: "input" },
        vibevoice_diarization: { key: "vibevoiceDiarization", event: "change", checkbox: true },
        vibevoice_chunk_size: { key: "vibevoiceChunkSize", event: "input" },
        vibevoice_temperature: { key: "vibevoiceTemperature", event: "input" },
        vibevoice_repetition_penalty: { key: "vibevoiceRepetitionPenalty", event: "input" },
        vibevoice_top_p: { key: "vibevoiceTopP", event: "input" },
        vibevoice_top_k: { key: "vibevoiceTopK", event: "input" },
        vibevoice_num_beams: { key: "vibevoiceNumBeams", event: "input" },
        vibevoice_max_new_tokens: { key: "vibevoiceMaxNewTokens", event: "input" },
    },
    tts: {
        tts_model: { key: "inputTtsModel", event: "change" },
        speaker_id: { key: "inputTtsSpeaker", event: "change" },
        temperature: { key: "inputTtsTemp", event: "input" },
        speed: { key: "inputTtsSpeed", event: "input" },
        repetition_penalty: { key: "inputTtsRepPenalty", event: "input" },
        // top_p/top_k do TTS existem na API, mas não têm controle nesta UI.
    },
};

function applyParamsToForm(engineParams) {
    let applied = 0;
    for (const [engine, fields] of Object.entries(engineParams || {})) {
        const fieldMap = FORM_FIELD_MAP[engine];
        if (!fieldMap) continue;
        for (const [fieldName, value] of Object.entries(fields || {})) {
            const spec = fieldMap[fieldName];
            if (!spec || value === null || value === undefined) continue;
            const el = elements[spec.key];
            if (!el) continue;
            if (spec.checkbox) el.checked = Boolean(value);
            else el.value = value;
            el.dispatchEvent(new Event(spec.event, { bubbles: true }));
            applied++;
        }
    }
    saveSettingsToStorage();
    return applied;
}

function collectParamsFromForm() {
    const collected = {};
    for (const [engine, fieldMap] of Object.entries(FORM_FIELD_MAP)) {
        collected[engine] = {};
        for (const [fieldName, spec] of Object.entries(fieldMap)) {
            if (fieldName.includes("prompt")) continue; // conteúdo do usuário fica fora de presets/perfis
            const el = elements[spec.key];
            if (!el) continue;
            collected[engine][fieldName] = spec.checkbox ? el.checked : el.value;
        }
    }
    return collected;
}

// Expostos para os módulos de presets/perfis e modo avançado.
window.applyParamsToForm = applyParamsToForm;
window.collectParamsFromForm = collectParamsFromForm;

// --- MONITORAMENTO DE HARDWARE ---
async function fetchSystemStatus() {
    try {
        const response = await fetch("/api/system-status");
        if (!response.ok) return;
        const data = await response.json();
        
        // Atualiza UI da CPU
        elements.cpuVal.textContent = `${data.cpu.percent}% (${data.cpu.cores} Cores)`;
        elements.cpuBar.style.width = `${data.cpu.percent}%`;
        
        // Atualiza UI da RAM
        const ramUsed = (data.ram.total_gb * (data.ram.used_percent / 100)).toFixed(1);
        elements.ramVal.textContent = `${ramUsed} / ${data.ram.total_gb} GB (${data.ram.used_percent}%)`;
        elements.ramBar.style.width = `${data.ram.used_percent}%`;
        
        // Atualiza UI da GPU (NVIDIA CUDA)
        if (data.gpu.available) {
            const vramUsedGb = (data.gpu.vram_allocated_mb / 1024).toFixed(2);
            const vramTotalGb = (data.gpu.vram_total_mb / 1024).toFixed(1);
            const gpuPercent = ((data.gpu.vram_allocated_mb / data.gpu.vram_total_mb) * 100) || 0;
            
            elements.gpuVal.textContent = `${data.gpu.name} | ${vramUsedGb} / ${vramTotalGb} GB`;
            elements.gpuBar.style.width = `${gpuPercent}%`;
            elements.gpuBar.style.backgroundColor = "var(--accent-cyan)";
            
            document.getElementById("recommendation-badge").textContent = "CUDA Disponível";
            document.getElementById("recommendation-badge").style.borderColor = "var(--accent-cyan)";
            document.getElementById("recommendation-badge").style.color = "var(--accent-cyan)";
        } else {
            elements.gpuVal.textContent = "Inativa / Não disponível";
            elements.gpuBar.style.width = "0%";
            
            document.getElementById("recommendation-badge").textContent = "Modo CPU";
            document.getElementById("recommendation-badge").style.borderColor = "var(--text-muted)";
            document.getElementById("recommendation-badge").style.color = "var(--text-muted)";
        }
    } catch (error) {
        console.error("Erro ao buscar status do sistema:", error);
    }
}

// --- ARRASTE E SOLTE (DRAG & DROP) ---
function setupDragAndDrop() {
    elements.dropZone.addEventListener("click", () => elements.fileInput.click());
    
    elements.dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        elements.dropZone.classList.add("dragover");
    });
    
    ["dragleave", "drop"].forEach(event => {
        elements.dropZone.addEventListener(event, () => {
            elements.dropZone.classList.remove("dragover");
        });
    });
    
    elements.dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });
}

function setupFileSelection() {
    elements.fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
    
    elements.btnCancelFile.addEventListener("click", () => {
        state.selectedFile = null;
        elements.activeFileBanner.style.display = "none";
        elements.dropZone.style.display = "flex";
        elements.transcribeActionArea.style.display = "none";
        elements.dualWorkspace.style.display = "none";
        elements.fileInput.value = "";
    });
}

function handleFileSelect(file) {
    // Validar tipo de arquivo
    if (!file.type.startsWith("audio/") && !file.name.endsWith(".m4a") && !file.name.endsWith(".mp3") && !file.name.endsWith(".wav")) {
        showToast("Por favor, selecione um arquivo de áudio válido.", true);
        return;
    }
    
    state.selectedFile = file;
    elements.selectedFileName.textContent = file.name;
    elements.selectedFileSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    
    // Atualiza visibilidade dos painéis
    elements.dropZone.style.display = "none";
    elements.activeFileBanner.style.display = "flex";
    elements.transcribeActionArea.style.display = "flex";
    
    // Configura o player de áudio com a URL local do arquivo selecionado
    elements.workspaceAudioPlayer.src = URL.createObjectURL(file);
}

// --- EXECUÇÃO E STREAMING DA TRANSCRIÇÃO ---
function setupActions() {
    elements.btnStartTranscription.addEventListener("click", startTranscriptionWorkflow);
    elements.btnCopyTranscript.addEventListener("click", copyTranscriptToClipboard);
    elements.btnDownloadTxt.addEventListener("click", downloadTranscriptTxt);
    
    // Alternar exibição de marcadores de tempo
    if (elements.btnToggleTimestamps) {
        elements.btnToggleTimestamps.addEventListener("click", () => {
            state.showTimestamps = !state.showTimestamps;
            elements.btnToggleTimestamps.classList.toggle("active", state.showTimestamps);
            elements.transcriptSegmentsList.classList.toggle("hide-timestamps", !state.showTimestamps);
        });
    }
    
    // Alternar exibição de falantes
    if (elements.btnToggleSpeakers) {
        elements.btnToggleSpeakers.addEventListener("click", () => {
            state.showSpeakers = !state.showSpeakers;
            elements.btnToggleSpeakers.classList.toggle("active", state.showSpeakers);
            elements.transcriptSegmentsList.classList.toggle("hide-speakers", !state.showSpeakers);
        });
    }
    
    // Parar transcrição em execução: primeiro cancela o job no SERVIDOR
    // (libera GPU/CPU), depois aborta o stream local.
    elements.btnStopTranscription.addEventListener("click", async () => {
        const jobId = state.currentJobId;
        if (jobId) {
            try {
                await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
                logClientEvent("transcription_cancel_requested", { details: { job_id: jobId } });
            } catch (err) {
                console.warn("Falha ao cancelar o job no servidor (o abort local continua):", err);
            }
        }
        if (state.abortController) {
            state.abortController.abort();
            state.abortController = null;
            stopTimer();
            setUIBusy(false);
            elements.progressStatus.textContent = "Transcrição interrompida pelo usuário.";
            elements.progressBarFill.style.width = "0%";
            elements.progressPercentage.textContent = "0%";
            showToast("Transcrição parada.", true);
        }
        state.currentJobId = null;
    });
    
    // Lógica para pesquisar termos no texto transcrito
    elements.searchTranscript.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        const segments = document.querySelectorAll(".segment-item");
        
        segments.forEach(seg => {
            const textEl = seg.querySelector(".segment-text");
            const originalText = textEl.textContent;
            
            if (!query) {
                textEl.innerHTML = originalText;
                seg.style.display = "block";
                return;
            }
            
            if (originalText.toLowerCase().includes(query)) {
                seg.style.display = "block";
                // Realça a correspondência de pesquisa (highlight)
                const regex = new RegExp(`(${query})`, "gi");
                textEl.innerHTML = originalText.replace(regex, "<mark>$1</mark>");
            } else {
                seg.style.display = "none";
            }
        });
    });

    // Captura a duração do áudio assim que as metadados são carregados
    elements.workspaceAudioPlayer.addEventListener("loadedmetadata", () => {
        if (elements.workspaceAudioPlayer.duration) {
            state.audioDuration = elements.workspaceAudioPlayer.duration;
            console.log("Duração do áudio capturada:", state.audioDuration);
        }
    });

    // --- LOGICA DE SÍNTESE DE VOZ (TTS) ---
    
    // Alternar modos principais (ASR vs TTS)
    if (elements.modeTabAsr && elements.modeTabTts) {
        elements.modeTabAsr.addEventListener("click", () => {
            elements.modeTabAsr.classList.add("active");
            elements.modeTabTts.classList.remove("active");
            
            elements.asrConfigsSidebar.style.display = "block";
            elements.ttsConfigsSidebar.style.display = "none";
            
            elements.asrWorkspaceContainer.style.display = "block";
            elements.ttsWorkspaceContainer.style.display = "none";
        });
        
        elements.modeTabTts.addEventListener("click", () => {
            elements.modeTabTts.classList.add("active");
            elements.modeTabAsr.classList.remove("active");
            
            elements.ttsConfigsSidebar.style.display = "block";
            elements.asrConfigsSidebar.style.display = "none";
            
            elements.ttsWorkspaceContainer.style.display = "block";
            elements.asrWorkspaceContainer.style.display = "none";
            
            // Inicializa conexão websocket ao entrar no modo TTS
            initTtsWebSocket();
        });
    }

    // Sliders de Configurações TTS
    if (elements.inputTtsTemp) {
        elements.inputTtsTemp.addEventListener("input", (e) => {
            elements.ttsTempValue.textContent = e.target.value;
        });
    }
    if (elements.inputTtsSpeed) {
        elements.inputTtsSpeed.addEventListener("input", (e) => {
            elements.ttsSpeedValue.textContent = e.target.value;
        });
    }
    if (elements.inputTtsRepPenalty) {
        elements.inputTtsRepPenalty.addEventListener("input", (e) => {
            elements.ttsRepValue.textContent = e.target.value;
        });
    }
    if (elements.inputTtsModel) {
        elements.inputTtsModel.addEventListener("change", () => {
            if (elements.inputTtsModel.value !== "realtime_0_5b") {
                state.lastLongformTtsModel = elements.inputTtsModel.value;
            }
        });
    }

    // Alternância de Abas TTS internas
    const ttsTabBtns = document.querySelectorAll(".tts-tab-btn");
    ttsTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            ttsTabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const mode = btn.getAttribute("data-tts-mode");
            document.querySelectorAll(".tts-mode-panel").forEach(p => p.style.display = "none");
            
            if (mode === "single") {
                if (elements.inputTtsModel.value === "realtime_0_5b") {
                    elements.inputTtsModel.value = state.lastLongformTtsModel || "tts_1_5b";
                }
                document.getElementById("tts-panel-single").style.display = "block";
            } else if (mode === "dialog") {
                if (elements.inputTtsModel.value === "realtime_0_5b") {
                    elements.inputTtsModel.value = state.lastLongformTtsModel || "tts_1_5b";
                }
                document.getElementById("tts-panel-dialog").style.display = "block";
            } else if (mode === "chat") {
                if (elements.inputTtsModel.value !== "realtime_0_5b") {
                    state.lastLongformTtsModel = elements.inputTtsModel.value;
                }
                elements.inputTtsModel.value = "realtime_0_5b";
                setTtsEngineStatus(elements.ttsEngineStatusChat, "Modelo em uso", "VibeVoice-Realtime-0.5B", false);
                document.getElementById("tts-panel-chat").style.display = "block";
                initTtsWebSocket();
            }
        });
    });

    // Enviar Requisição de Síntese Simples (TTS-1.5B)
    if (elements.btnGenerateTts) {
        elements.btnGenerateTts.addEventListener("click", async () => {
            const text = elements.ttsInputText.value.trim();
            if (!text) {
                showToast("Por favor, digite algum texto para sintetizar.", true);
                return;
            }
            
            elements.btnGenerateTts.disabled = true;
            elements.btnGenerateTts.textContent = "Sintetizando... ⏳";
            setTtsEngineStatus(elements.ttsEngineStatusSingle, "Solicitado", getSelectedTtsModelLabel(), false);
            logClientEvent("tts_single_requested", {
                details: {
                    text_length: text.length,
                    requested_model: elements.inputTtsModel.value
                }
            });
            
            const formData = new FormData();
            formData.append("text", text);
            formData.append("tts_model", elements.inputTtsModel.value);
            formData.append("speaker_id", elements.inputTtsSpeaker.value);
            formData.append("speed", elements.inputTtsSpeed.value);
            // Voz da biblioteca + parâmetros REAIS do 1.5B (cfg/steps/seed/política)
            if (window.collectTtsExtras) {
                for (const [key, value] of Object.entries(window.collectTtsExtras("single"))) {
                    formData.append(key, value);
                }
            }

            try {
                const response = await fetch("/api/tts/generate", {
                    method: "POST",
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(await readErrorMessage(response, "Erro na geração do áudio."));
                }
                let engineLabel = response.headers.get("X-Escriba-TTS-Engine") || getSelectedTtsModelLabel();
                const voicesUsed = response.headers.get("X-Escriba-TTS-Voices");
                if (voicesUsed) engineLabel += ` · ${voicesUsed}`;
                const fallbackUsed = response.headers.get("X-Escriba-TTS-Fallback") === "true";

                const blob = await response.blob();
                const audioUrl = URL.createObjectURL(blob);

                elements.ttsAudioPlayerSingle.src = audioUrl;
                elements.btnDownloadTtsSingle.href = audioUrl;

                elements.ttsResultSingle.style.display = "block";
                setTtsEngineStatus(
                    elements.ttsEngineStatusSingle,
                    fallbackUsed ? "Fallback em uso" : "Modelo em uso",
                    engineLabel,
                    fallbackUsed
                );
                logClientEvent("tts_single_completed", {
                    details: {
                        engine_label: engineLabel,
                        fallback: fallbackUsed,
                        output_bytes: blob.size
                    }
                });
                showToast("Voz sintetizada com sucesso!");
            } catch (err) {
                console.error(err);
                setTtsEngineStatus(elements.ttsEngineStatusSingle, "Falha", err.message || "Erro na geração", true);
                logClientEvent("tts_single_error", { severity: "error", message: err.message });
                showToast(err.message || "Falha ao gerar síntese de voz.", true);
            } finally {
                elements.btnGenerateTts.disabled = false;
                elements.btnGenerateTts.textContent = "🔊 Sintetizar Voz";
            }
        });
    }

    // Enviar Requisição de Síntese de Diálogo (TTS-1.5B)
    if (elements.btnGenerateDialog) {
        elements.btnGenerateDialog.addEventListener("click", async () => {
            const text = elements.ttsInputDialog.value.trim();
            if (!text) {
                showToast("Por favor, escreva o roteiro do diálogo.", true);
                return;
            }
            
            elements.btnGenerateDialog.disabled = true;
            elements.btnGenerateDialog.textContent = "Processando Diálogo... ⏳";
            setTtsEngineStatus(elements.ttsEngineStatusDialog, "Solicitado", getSelectedTtsModelLabel(), false);
            logClientEvent("tts_dialog_requested", {
                details: {
                    text_length: text.length,
                    requested_model: elements.inputTtsModel.value
                }
            });
            
            const formData = new FormData();
            formData.append("text", text);
            formData.append("tts_model", elements.inputTtsModel.value);
            formData.append("speaker_id", elements.inputTtsSpeaker.value);
            formData.append("speed", elements.inputTtsSpeed.value);
            // No diálogo, inclui o mapa Speaker N -> voz da biblioteca
            if (window.collectTtsExtras) {
                for (const [key, value] of Object.entries(window.collectTtsExtras("dialog"))) {
                    formData.append(key, value);
                }
            }

            try {
                const response = await fetch("/api/tts/generate", {
                    method: "POST",
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(await readErrorMessage(response, "Erro na geração do diálogo."));
                }
                let engineLabel = response.headers.get("X-Escriba-TTS-Engine") || getSelectedTtsModelLabel();
                const voicesUsed = response.headers.get("X-Escriba-TTS-Voices");
                if (voicesUsed) engineLabel += ` · ${voicesUsed}`;
                const fallbackUsed = response.headers.get("X-Escriba-TTS-Fallback") === "true";
                
                const blob = await response.blob();
                const audioUrl = URL.createObjectURL(blob);
                
                elements.ttsAudioPlayerDialog.src = audioUrl;
                elements.btnDownloadTtsDialog.href = audioUrl;
                
                elements.ttsResultDialog.style.display = "block";
                setTtsEngineStatus(
                    elements.ttsEngineStatusDialog,
                    fallbackUsed ? "Fallback em uso" : "Modelo em uso",
                    engineLabel,
                    fallbackUsed
                );
                logClientEvent("tts_dialog_completed", {
                    details: {
                        engine_label: engineLabel,
                        fallback: fallbackUsed,
                        output_bytes: blob.size
                    }
                });
                showToast("Diálogo sintetizado com sucesso!");
            } catch (err) {
                console.error(err);
                setTtsEngineStatus(elements.ttsEngineStatusDialog, "Falha", err.message || "Erro na geração", true);
                logClientEvent("tts_dialog_error", { severity: "error", message: err.message });
                showToast(err.message || "Falha ao gerar diálogo.", true);
            } finally {
                elements.btnGenerateDialog.disabled = false;
                elements.btnGenerateDialog.textContent = "👥 Gerar Conversa Completa";
            }
        });
    }

    // Chat / Assistente em Tempo Real (Realtime-0.5B)
    let ttsWs = null;
    let audioPlayer = null;

    class AudioStreamPlayer {
        constructor(sampleRate = 24000) {
            this.sampleRate = sampleRate;
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.nextStartTime = 0;
        }
        playChunk(pcmInt16Bytes) {
            const int16Array = new Int16Array(pcmInt16Bytes);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }
            const audioBuffer = this.audioCtx.createBuffer(1, float32Array.length, this.sampleRate);
            audioBuffer.getChannelData(0).set(float32Array);
            
            const source = this.audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioCtx.destination);
            
            const startTime = Math.max(this.audioCtx.currentTime, this.nextStartTime);
            source.start(startTime);
            this.nextStartTime = startTime + audioBuffer.duration;
        }
        reset() {
            this.nextStartTime = 0;
        }
    }

    function initTtsWebSocket() {
        if (ttsWs && (ttsWs.readyState === WebSocket.OPEN || ttsWs.readyState === WebSocket.CONNECTING)) return;
        
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/api/tts/stream`;
        
        console.log("Conectando ao WebSocket de TTS em:", wsUrl);
        ttsWs = new WebSocket(wsUrl);
        ttsWs.binaryType = "arraybuffer";
        
        audioPlayer = new AudioStreamPlayer();
        
        ttsWs.onmessage = (event) => {
            if (typeof event.data === "string") {
                const data = JSON.parse(event.data);
                if (data.type === "stream_end") {
                    console.log("Fim do bloco de voz.");
                } else if (data.type === "engine_status") {
                    setTtsEngineStatus(
                        elements.ttsEngineStatusChat,
                        data.fallback ? "Fallback em uso" : "Modelo em uso",
                        data.engine_label || "VibeVoice-Realtime-0.5B",
                        Boolean(data.fallback)
                    );
                    logClientEvent("tts_chat_engine_status", {
                        details: {
                            engine_label: data.engine_label,
                            fallback: Boolean(data.fallback)
                        }
                    });
                } else if (data.type === "error") {
                    setTtsEngineStatus(elements.ttsEngineStatusChat, "Falha", data.message || "Erro no streaming", true);
                    logClientEvent("tts_chat_error", { severity: "error", message: data.message });
                    showToast("Erro do assistente: " + data.message, true);
                }
            } else if (event.data instanceof ArrayBuffer) {
                // Toca o chunk de áudio binário
                audioPlayer.playChunk(event.data);
            }
        };
        
        ttsWs.onclose = () => {
            console.log("WebSocket de TTS encerrado.");
        };
        
        ttsWs.onerror = (e) => {
            console.error("Erro no WebSocket de TTS:", e);
        };
    }

    if (elements.btnSendTtsChat) {
        const sendChatMessage = () => {
            const inputVal = elements.ttsChatInput.value.trim();
            if (!inputVal) return;
            
            // Renderiza bolha do usuário
            const userBubble = document.createElement("div");
            userBubble.className = "chat-bubble user";
            userBubble.textContent = inputVal;
            elements.ttsChatMessages.appendChild(userBubble);
            elements.ttsChatInput.value = "";
            elements.ttsChatMessages.scrollTop = elements.ttsChatMessages.scrollHeight;
            
            // Garante que o WS está pronto
            initTtsWebSocket();
            
            // Envia a requisição de fala via WebSocket quando conectado
            const payload = {
                text: inputVal,
                speaker_id: elements.inputTtsSpeaker.value,
                temperature: parseFloat(elements.inputTtsTemp.value),
                repetition_penalty: parseFloat(elements.inputTtsRepPenalty.value),
                speed: parseFloat(elements.inputTtsSpeed.value)
            };
            setTtsEngineStatus(elements.ttsEngineStatusChat, "Solicitado", "VibeVoice-Realtime-0.5B", false);
            logClientEvent("tts_chat_requested", {
                details: {
                    text_length: inputVal.length,
                    requested_model: "realtime_0_5b"
                }
            });
            
            // Se o socket estiver abrindo, aguarda e envia
            if (ttsWs.readyState === WebSocket.CONNECTING) {
                ttsWs.addEventListener("open", () => {
                    ttsWs.send(JSON.stringify(payload));
                });
            } else if (ttsWs.readyState === WebSocket.OPEN) {
                audioPlayer.reset();
                ttsWs.send(JSON.stringify(payload));
            } else {
                showToast("Erro na conexão em tempo real.", true);
            }
            
            // Simula uma resposta visual após 500ms
            setTimeout(() => {
                const assistantBubble = document.createElement("div");
                assistantBubble.className = "chat-bubble assistant";
                assistantBubble.textContent = `Falando: "${inputVal}"`;
                elements.ttsChatMessages.appendChild(assistantBubble);
                elements.ttsChatMessages.scrollTop = elements.ttsChatMessages.scrollHeight;
            }, 300);
        };

        elements.btnSendTtsChat.addEventListener("click", sendChatMessage);
        elements.ttsChatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                sendChatMessage();
            }
        });
    }
}

function startTimer() {
    state.startTime = Date.now();
    elements.timeElapsed.textContent = "Decorrido: 00:00";
    elements.timeEta.textContent = "Previsão (ETA): Calculando...";
    
    state.timerInterval = setInterval(() => {
        const diffMs = Date.now() - state.startTime;
        const h = Math.floor(diffMs / 3600000);
        const m = Math.floor((diffMs % 3600000) / 60000);
        const s = Math.floor((diffMs % 60000) / 1000);
        
        const hStr = h > 0 ? `${h.toString().padStart(2, '0')}:` : "";
        elements.timeElapsed.textContent = `Decorrido: ${hStr}${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

async function startTranscriptionWorkflow() {
    if (!state.selectedFile) return;
    
    // Desabilitar controles e botões durante processamento
    setUIBusy(true);
    elements.transcribeActionArea.style.display = "flex";
    elements.progressContainer.style.display = "block";
    const engineName = elements.inputEngine.value === "vibevoice" ? "VibeVoice" : "Whisper";
    elements.progressStatus.textContent = `Enviando arquivo ao ${engineName}...`;
    elements.progressBarFill.style.width = "0%";
    elements.progressPercentage.textContent = "0%";
    elements.transcriptSegmentsList.innerHTML = "";
    elements.dualWorkspace.style.display = "none";
    state.currentJobId = null;
    setModelStatus(elements.asrModelStatus, "Solicitado", getSelectedAsrModelLabel(), false);
    logClientEvent("transcription_requested", {
        details: {
            active_mode: state.activeMode,
            engine: elements.inputEngine.value,
            file_size: state.selectedFile ? state.selectedFile.size : null,
            file_type: state.selectedFile ? state.selectedFile.type : null
        }
    });
    
    startTimer();
    
    state.abortController = new AbortController();
    
    const formData = new FormData();
    formData.append("file", state.selectedFile);
    
    let endpoint = "/api/transcribe";
    if (elements.inputEngine.value === "vibevoice") {
        endpoint = "/api/transcribe-vibevoice";
        formData.append("vibevoice_prompt", elements.vibevoicePrompt.value);
        formData.append("vibevoice_diarization", elements.vibevoiceDiarization.checked);
        formData.append("vibevoice_chunk_size", elements.vibevoiceChunkSize.value);
        formData.append("vibevoice_temperature", elements.vibevoiceTemperature.value);
        formData.append("vibevoice_repetition_penalty", elements.vibevoiceRepetitionPenalty.value);
        formData.append("vibevoice_top_p", elements.vibevoiceTopP.value);
        formData.append("vibevoice_top_k", elements.vibevoiceTopK.value);
        formData.append("vibevoice_num_beams", elements.vibevoiceNumBeams.value);
        formData.append("vibevoice_max_new_tokens", elements.vibevoiceMaxNewTokens.value);
    } else {
        formData.append("model", elements.inputModel.value);
        formData.append("device", elements.inputDevice.value);
        formData.append("compute_type", elements.inputCompute.value);
        formData.append("beam_size", elements.inputBeam.value);
        formData.append("vad_filter", elements.inputVad.checked);
        formData.append("cpu_threads", elements.inputThreads.value);
        formData.append("language", elements.whisperLanguage.value);
        formData.append("whisper_prompt", elements.whisperPrompt.value);
        formData.append("whisper_temperature", elements.whisperTemperature.value);
    }
    
    try {
        // Envia requisição HTTP POST e recebe como stream SSE
        const response = await fetch(endpoint, {
            method: "POST",
            body: formData,
            signal: state.abortController.signal
        });
        
        if (!response.ok) {
            throw new Error(`Erro no servidor: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let buffer = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            
            // O último elemento pode ser incompleto, mantemos no buffer
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const jsonStr = line.substring(6);
                    try {
                        const payload = JSON.parse(jsonStr);
                        handleSSEPayload(payload);
                    } catch (e) {
                        console.warn("Falha ao analisar JSON do stream SSE:", e);
                    }
                }
            }
        }
        
    } catch (error) {
        if (error.name === "AbortError") {
            console.log("Fluxo interrompido via AbortController pelo usuario.");
            return; // O tratador de clique ja cuida de limpar a UI
        }
        console.error("Erro na requisição de transcrição:", error);
        logClientEvent("transcription_request_error", { severity: "error", message: error.message });
        showToast(error.message || "Erro desconhecido durante transcrição.", true);
        elements.progressStatus.textContent = "Ocorreu um erro no processamento.";
        setModelStatus(elements.asrModelStatus, "Falha", error.message || "Erro no modelo", true);
        stopTimer();
        setUIBusy(false);
    }

}

function handleSSEPayload(data) {
    if (data.type === "job") {
        // Identificador do job no servidor; usado pelo botão Parar para
        // cancelar o processamento de verdade (não só o stream local).
        state.currentJobId = data.job_id;
    }
    else if (data.type === "cancelled") {
        stopTimer();
        setUIBusy(false);
        state.currentJobId = null;
        elements.progressStatus.textContent = data.message || "Transcrição cancelada no servidor.";
        logClientEvent("transcription_cancelled", { details: { message: data.message } });
        showToast("Transcrição cancelada.", true);
    }
    else if (data.type === "model_status") {
        setModelStatus(
            elements.asrModelStatus,
            data.caption || (data.fallback ? "Fallback em uso" : "Modelo em uso"),
            formatModelStatusLabel(data),
            Boolean(data.fallback)
        );
        logClientEvent("transcription_model_status", {
            details: {
                engine_label: data.engine_label,
                device: data.device,
                compute_type: data.compute_type,
                fallback: Boolean(data.fallback)
            }
        });
    }
    else if (data.type === "status") {
        elements.progressStatus.textContent = data.message;
    }
    else if (data.type === "download_progress") {
        elements.progressBarFill.style.width = `${data.percent}%`;
        elements.progressPercentage.textContent = `${data.percent}%`;
        elements.progressStatus.textContent = `Baixando modelo Whisper: ${data.percent}% @ ${data.speed_mb} MB/s`;
        elements.timeEta.textContent = `Previsão: Baixando arquivos da IA...`;
    }
    else if (data.type === "meta") {
        state.audioDuration = data.duration;
        elements.progressStatus.textContent = `Áudio detectado (${formatTime(data.duration)}). Processando...`;
        
        // Exibe o painel duplo imediatamente para mostrar o texto em tempo real
        elements.dualWorkspace.style.display = "grid";
    } 
    else if (data.type === "progress") {
        const percent = data.progress;
        elements.progressBarFill.style.width = `${percent}%`;
        elements.progressPercentage.textContent = `${percent}%`;
        
        // Adiciona dinamicamente os blocos de texto que vão chegando à interface
        appendTranscriptSegment(data.segment);
        
        // Estimação do tempo restante (ETA) baseada no rendimento
        if (state.startTime && percent > 0) {
            const timeElapsedMs = Date.now() - state.startTime;
            const totalEstimatedMs = (timeElapsedMs / percent) * 100;
            const etaMs = Math.max(0, totalEstimatedMs - timeElapsedMs);
            elements.timeEta.textContent = `Previsão (ETA): ${formatTime(etaMs / 1000)}`;
        }
    } 
    else if (data.type === "text_chunk") {
        // Exibe o texto sendo gerado em tempo real
        showRealtimeTextPreview(data.text);
    }

    else if (data.type === "done") {
        stopTimer();
        setUIBusy(false);
        state.currentJobId = null;
        elements.progressStatus.textContent = "Transcrição concluída com sucesso!";
        elements.progressBarFill.style.width = "100%";
        elements.progressPercentage.textContent = "100%";
        logClientEvent("transcription_completed", {
            details: {
                segment_count: Array.isArray(data.full_transcript) ? data.full_transcript.length : 0
            }
        });
        showToast("Sucesso! Áudio transcrevido.");
        
        // Exibe o painel duplo
        elements.dualWorkspace.style.display = "grid";
        
        // Re-desenha a lista completa de segmentos finalizada e limpa duplicatas
        renderFinalTranscript(data.full_transcript);
        
        // Rola até o final
        elements.transcriptSegmentsList.scrollTop = 0;
    }
    else if (data.type === "error") {
        stopTimer();
        setUIBusy(false);
        state.currentJobId = null;
        elements.progressStatus.textContent = `Erro: ${data.message}`;
        setModelStatus(elements.asrModelStatus, "Falha", data.message || "Erro no modelo", true);
        logClientEvent("transcription_stream_error", { severity: "error", message: data.message });
        showToast(`Erro na transcrição: ${data.message}`, true);
    }
}

function setUIBusy(isBusy) {
    elements.btnStartTranscription.disabled = isBusy;
    elements.btnCancelFile.disabled = isBusy;
    elements.inputModel.disabled = isBusy;
    elements.inputDevice.disabled = isBusy;
    elements.inputCompute.disabled = isBusy;
    elements.inputBeam.disabled = isBusy;
    elements.inputVad.disabled = isBusy;
    elements.inputThreads.disabled = isBusy;
}

// --- CONVERSÕES E ELEMENTOS DE RENDERIZAÇÃO ---
function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (h > 0) {
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function appendTranscriptSegment(segment) {
    // Evita duplicar elementos na chegada em tempo real
    const existingId = `seg-${segment.start.toFixed(2)}`;
    if (document.getElementById(existingId)) return;
    
    const div = document.createElement("div");
    div.className = "segment-item";
    div.id = existingId;
    
    const meta = document.createElement("div");
    meta.className = "segment-meta";
    
    const time = document.createElement("span");
    time.className = "segment-time";
    time.textContent = `[${formatTime(segment.start)}]`;
    time.addEventListener("click", () => {
        elements.workspaceAudioPlayer.currentTime = segment.start;
        elements.workspaceAudioPlayer.play();
    });
    
    meta.appendChild(time);
    
    if (segment.speaker) {
        const speakerSpan = document.createElement("span");
        speakerSpan.className = "segment-speaker";
        speakerSpan.textContent = `(${segment.speaker})`;
        speakerSpan.style.fontWeight = "600";
        speakerSpan.style.fontSize = "11.5px";
        speakerSpan.style.marginLeft = "8px";
        speakerSpan.style.padding = "2px 6px";
        speakerSpan.style.borderRadius = "4px";
        speakerSpan.style.background = "rgba(255,255,255,0.05)";
        
        // Colore falantes de forma diferente para destacar
        if (segment.speaker.toLowerCase().includes("1") || segment.speaker.toLowerCase().includes("a")) {
            speakerSpan.style.color = "var(--accent-cyan)";
            speakerSpan.style.borderColor = "var(--accent-cyan)";
        } else {
            speakerSpan.style.color = "var(--accent-purple)";
            speakerSpan.style.borderColor = "var(--accent-purple)";
        }
        meta.appendChild(speakerSpan);
    }
    
    const text = document.createElement("p");
    text.className = "segment-text";
    text.textContent = segment.text;
    
    div.appendChild(meta);
    div.appendChild(text);
    
    elements.transcriptSegmentsList.appendChild(div);
    elements.transcriptSegmentsList.scrollTop = elements.transcriptSegmentsList.scrollHeight;
}


function renderFinalTranscript(segments) {
    elements.transcriptSegmentsList.innerHTML = "";
    state.transcriptionSegments = segments;
    segments.forEach(seg => appendTranscriptSegment(seg));
}

function showRealtimeTextPreview(text) {
    // Garante que o container duplo esteja visível para ver o texto fluindo
    elements.dualWorkspace.style.display = "grid";
    
    let previewEl = document.getElementById("vibevoice-live-preview");
    if (!previewEl) {
        previewEl = document.createElement("div");
        previewEl.className = "segment-item";
        previewEl.id = "vibevoice-live-preview";
        previewEl.style.borderLeft = "2px dashed var(--accent-cyan)";
        previewEl.style.background = "rgba(255, 255, 255, 0.02)";
        previewEl.style.paddingLeft = "10px";
        previewEl.style.borderRadius = "4px";
        previewEl.style.marginTop = "8px";
        
        const meta = document.createElement("div");
        meta.className = "segment-meta";
        
        const time = document.createElement("span");
        time.className = "segment-time";
        time.textContent = "[Processando em tempo real...]";
        meta.appendChild(time);
        
        const textP = document.createElement("p");
        textP.className = "segment-text";
        textP.id = "vibevoice-live-preview-text";
        textP.style.fontStyle = "italic";
        
        previewEl.appendChild(meta);
        previewEl.appendChild(textP);
        
        elements.transcriptSegmentsList.appendChild(previewEl);
    }
    
    const textP = document.getElementById("vibevoice-live-preview-text");
    if (textP) {
        textP.textContent += text;
    }
    
    // Rola para manter o texto novo visível
    elements.transcriptSegmentsList.scrollTop = elements.transcriptSegmentsList.scrollHeight;
    
    // Atualiza a barra de progresso dinamicamente
    if (state.audioDuration > 0) {
        const currentLength = textP.textContent.length;
        // Mapeia aproximadamente: estima que a fala tenha ~12 caracteres por segundo
        const expectedLength = Math.max(100, state.audioDuration * 12);
        const percent = Math.min(95, (currentLength / expectedLength) * 100);
        
        elements.progressBarFill.style.width = `${percent.toFixed(1)}%`;
        elements.progressPercentage.textContent = `${percent.toFixed(0)}%`;
        elements.progressStatus.textContent = `Transcrevendo com VibeVoice: texto em tempo real gerado...`;
        
        // Atualiza a previsão (ETA) baseada no tempo decorrido e progresso estimado
        if (state.startTime && percent > 0) {
            const timeElapsedMs = Date.now() - state.startTime;
            const totalEstimatedMs = (timeElapsedMs / percent) * 100;
            const etaMs = Math.max(0, totalEstimatedMs - timeElapsedMs);
            elements.timeEta.textContent = `Previsão (ETA): ${formatTime(etaMs / 1000)}`;
        }
    } else {
        // Se não soubermos a duração (ex. falha nas metadados), fazemos um progresso simulado suave
        let currentPercent = parseFloat(elements.progressBarFill.style.width) || 0;
        if (currentPercent < 90) {
            currentPercent += 0.5;
            elements.progressBarFill.style.width = `${currentPercent.toFixed(1)}%`;
            elements.progressPercentage.textContent = `${currentPercent.toFixed(0)}%`;
        }
        elements.progressStatus.textContent = `Transcrevendo com VibeVoice...`;
    }
}

// --- OPERAÇÕES DE EXPORTAÇÃO E CÓPIA ---
function getFormattedTranscriptText() {
    return state.transcriptionSegments
        .map(s => {
            let prefix = "";
            if (state.showTimestamps) {
                prefix += `[${formatTime(s.start)}] `;
            }
            if (state.showSpeakers && s.speaker) {
                prefix += `(${s.speaker}) `;
            }
            return `${prefix}${s.text}`;
        })
        .join("\n");
}

function copyTranscriptToClipboard() {
    if (state.transcriptionSegments.length === 0) return;
    
    const text = getFormattedTranscriptText();
        
    navigator.clipboard.writeText(text)
        .then(() => showToast("Transcrição copiada com sucesso!"))
        .catch(err => showToast("Erro ao copiar transcrição.", true));
}

function downloadTranscriptTxt() {
    if (state.transcriptionSegments.length === 0) return;
    
    const text = getFormattedTranscriptText();
        
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement("a");
    a.href = url;
    a.download = `Transcrição_${state.selectedFile ? state.selectedFile.name.split('.')[0] : 'Sessão'}.txt`;
    document.body.appendChild(a);
    a.click();
    
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Arquivo TXT baixado com sucesso!");
}


function setupInputModes() {
    const tabs = document.querySelectorAll("#asr-workspace-container .tab-btn:not(.tts-tab-btn)");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const mode = tab.dataset.mode;
            state.activeMode = mode;
            
            // Oculta todos os painéis de entrada
            elements.dropZone.style.display = "none";
            elements.micRecordPanel.style.display = "none";
            elements.micLivePanel.style.display = "none";
            elements.activeFileBanner.style.display = "none";
            elements.transcribeActionArea.style.display = "none";
            
            // Oculta/Exibe configuração de tamanho do trecho na barra lateral
            if (mode === "live") {
                elements.configChunkSize.style.display = "flex";
            } else {
                elements.configChunkSize.style.display = "none";
            }
            
            // Exibe o painel do modo selecionado
            if (mode === "file") {
                setModelStatus(elements.asrModelStatus, "Modelo em uso", "Aguardando transcrição", false);
                if (state.selectedFile) {
                    elements.activeFileBanner.style.display = "flex";
                    elements.transcribeActionArea.style.display = "flex";
                } else {
                    elements.dropZone.style.display = "flex";
                }
            } else if (mode === "record") {
                setModelStatus(elements.asrModelStatus, "Modelo em uso", "Aguardando transcrição", false);
                elements.micRecordPanel.style.display = "flex";
            } else if (mode === "live") {
                setModelStatus(elements.asrLiveModelStatus, "Modelo em uso", "Aguardando transmissão", false);
                elements.micLivePanel.style.display = "flex";
            }
        });
    });
}

function setupMicRecord() {
    elements.btnStartMicRecord.addEventListener("click", async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            state.audioChunks = [];
            state.mediaRecorder = new MediaRecorder(stream);
            
            state.mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    state.audioChunks.push(e.data);
                }
            };
            
            state.mediaRecorder.onstop = () => {
                const blob = new Blob(state.audioChunks, { type: "audio/webm" });
                const file = new File([blob], `gravacao_${new Date().toISOString().slice(0,10)}.webm`, { type: "audio/webm" });
                
                // Salva o arquivo no estado e atualiza o banner
                state.selectedFile = file;
                elements.selectedFileName.textContent = file.name;
                elements.selectedFileSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
                elements.workspaceAudioPlayer.src = URL.createObjectURL(file);
                
                elements.micRecordStatus.textContent = "Gravação concluída. Iniciando transcrição...";
                
                // Restaura botões
                elements.btnStartMicRecord.style.display = "inline-flex";
                elements.btnPauseMicRecord.style.display = "none";
                elements.btnStopMicRecord.style.display = "none";
                elements.btnPauseMicRecord.textContent = "⏸️ Pausar";
                state.isRecordingPaused = false;
                
                // Dispara a transcrição automaticamente
                startTranscriptionWorkflow();
            };
            
            state.mediaRecorder.start();
            state.recordingSeconds = 0;
            state.isRecordingPaused = false;
            elements.recordingTimer.textContent = "00:00";
            elements.micRecordStatus.textContent = "🔴 Gravando áudio local...";
            logClientEvent("microphone_recording_started");
            
            elements.btnStartMicRecord.style.display = "none";
            elements.btnPauseMicRecord.style.display = "inline-flex";
            elements.btnStopMicRecord.style.display = "inline-flex";
            
            // Inicia o timer visual
            if (state.recordingTimerInterval) clearInterval(state.recordingTimerInterval);
            state.recordingTimerInterval = setInterval(() => {
                if (!state.isRecordingPaused) {
                    state.recordingSeconds++;
                    const m = Math.floor(state.recordingSeconds / 60);
                    const s = state.recordingSeconds % 60;
                    elements.recordingTimer.textContent = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                }
            }, 1000);
            
        } catch (err) {
            console.error("Erro ao acessar microfone para gravação:", err);
            logClientEvent("microphone_recording_error", { severity: "error", message: err.message });
            showToast("Não foi possível acessar o microfone.", true);
        }
    });
    
    elements.btnPauseMicRecord.addEventListener("click", () => {
        if (!state.mediaRecorder) return;
        
        if (state.mediaRecorder.state === "recording") {
            state.mediaRecorder.pause();
            state.isRecordingPaused = true;
            elements.btnPauseMicRecord.textContent = "▶️ Retomar";
            elements.micRecordStatus.textContent = "⏸️ Gravação pausada";
        } else if (state.mediaRecorder.state === "paused") {
            state.mediaRecorder.resume();
            state.isRecordingPaused = false;
            elements.btnPauseMicRecord.textContent = "⏸️ Pausar";
            elements.micRecordStatus.textContent = "🔴 Gravando áudio local...";
        }
    });
    
    elements.btnStopMicRecord.addEventListener("click", () => {
        if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
            logClientEvent("microphone_recording_stopped", {
                details: {
                    duration_seconds: state.recordingSeconds
                }
            });
            state.mediaRecorder.stop();
            // Para as tracks do microfone
            state.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            
            if (state.recordingTimerInterval) {
                clearInterval(state.recordingTimerInterval);
                state.recordingTimerInterval = null;
            }
        }
    });
}

function setupMicLive() {
    elements.btnStartMicLive.addEventListener("click", async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Configura a URL do WebSocket baseado na URL da página
            const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            const wsUrl = `${protocol}//${window.location.host}/api/live-transcribe`;
            
            elements.micLiveStatus.textContent = "Conectando ao servidor de streaming...";
            elements.btnStartMicLive.disabled = true;
            state.liveStopping = false;
            setModelStatus(elements.asrLiveModelStatus, "Solicitado", getSelectedAsrModelLabel(), false);
            logClientEvent("live_transcription_requested", {
                details: {
                    chunk_size_seconds: parseInt(elements.inputChunkSize.value) || 5
                }
            });
            
            state.liveSocket = new WebSocket(wsUrl);
            
            state.liveSocket.onopen = () => {
                // Envia dados de configuração ao conectar
                const config = {
                    model: elements.inputModel.value,
                    device: elements.inputDevice.value,
                    compute_type: elements.inputCompute.value,
                    beam_size: elements.inputBeam.value,
                    vad_filter: elements.inputVad.checked,
                    cpu_threads: elements.inputThreads.value,
                    language: "pt" // Força português para melhor acurácia em tempo real
                };
                state.liveSocket.send(JSON.stringify(config));
                
                // Limpa transcrição anterior e exibe painel duplo
                elements.transcriptSegmentsList.innerHTML = "";
                elements.dualWorkspace.style.display = "grid";
                elements.workspaceAudioPlayer.src = ""; // Sem player de arquivo no ao vivo
            };
            
            state.liveSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === "status") {
                        elements.micLiveStatus.textContent = data.message;
                    }
                    else if (data.type === "model_status") {
                        setModelStatus(
                            elements.asrLiveModelStatus,
                            data.caption || (data.fallback ? "Fallback em uso" : "Modelo em uso"),
                            formatModelStatusLabel(data),
                            Boolean(data.fallback)
                        );
                        logClientEvent("live_transcription_model_status", {
                            details: {
                                engine_label: data.engine_label,
                                device: data.device,
                                compute_type: data.compute_type,
                                fallback: Boolean(data.fallback)
                            }
                        });
                    }
                    else if (data.type === "ready") {
                        elements.micLiveStatus.textContent = "⚡ Transmitindo áudio... Fale agora!";
                        logClientEvent("live_transcription_ready");
                        elements.btnStartMicLive.style.display = "none";
                        elements.btnStartMicLive.disabled = false;
                        elements.btnStopMicLive.style.display = "inline-flex";
                        
                        // Inicia gravação contínua em fatias
                        const chunkSizeSec = parseInt(elements.inputChunkSize.value) || 5;
                        startLiveChunkRecorder(stream, chunkSizeSec);
                    }
                    else if (data.type === "progress") {
                        // O servidor retorna a lista completa de segmentos a cada chunk processado
                        renderFinalTranscript(data.segments);
                    }
                    else if (data.type === "error") {
                        setModelStatus(elements.asrLiveModelStatus, "Falha", data.message || "Erro no modelo", true);
                        logClientEvent("live_transcription_error", { severity: "error", message: data.message });
                        showToast(data.message, true);
                        stopLiveStreaming(stream);
                    }
                } catch (err) {
                    console.warn("Erro ao analisar mensagem WebSocket:", err);
                }
            };
            
            state.liveSocket.onclose = () => {
                console.log("Conexão WebSocket de streaming encerrada.");
                stopLiveStreaming(stream);
            };
            
            state.liveSocket.onerror = (err) => {
            console.error("Erro no WebSocket:", err);
            setModelStatus(elements.asrLiveModelStatus, "Falha", "Erro de conexão com o servidor", true);
            logClientEvent("live_websocket_error", { severity: "error", message: "Erro de conexão com o servidor." });
            showToast("Erro de conexão com o servidor.", true);
            stopLiveStreaming(stream);
            };
            
        } catch (err) {
            console.error("Erro ao iniciar microfone para tempo real:", err);
            setModelStatus(elements.asrLiveModelStatus, "Falha", "Microfone indisponível", true);
            logClientEvent("live_microphone_error", { severity: "error", message: err.message });
            showToast("Não foi possível acessar o microfone para tempo real.", true);
            elements.btnStartMicLive.disabled = false;
            elements.btnStartMicLive.style.display = "inline-flex";
            elements.btnStopMicLive.style.display = "none";
        }
    });
    
    elements.btnStopMicLive.addEventListener("click", () => {
        if (state.liveSocket && state.liveSocket.readyState === WebSocket.OPEN) {
            state.liveSocket.send(JSON.stringify({ action: "stop" }));
        }
        stopLiveStreaming();
    });
}

function stopLiveStreaming(stream = null) {
    state.liveStopping = true;
    elements.btnStartMicLive.style.display = "inline-flex";
    elements.btnStartMicLive.disabled = false;
    elements.btnStopMicLive.style.display = "none";
    elements.micLiveStatus.textContent = "Transmissão encerrada.";
    setModelStatus(elements.asrLiveModelStatus, "Encerrado", "Nenhum modelo rodando", false);
    logClientEvent("live_transcription_stopped");

    if (state.liveChunkTimer) {
        clearTimeout(state.liveChunkTimer);
        state.liveChunkTimer = null;
    }

    if (state.liveMediaRecorder && state.liveMediaRecorder.state !== "inactive") {
        try {
            state.liveMediaRecorder.stop();
        } catch(e){}
    }
    
    // Para as tracks de áudio
    if (state.liveMediaRecorder && state.liveMediaRecorder.stream) {
        state.liveMediaRecorder.stream.getTracks().forEach(t => t.stop());
    } else if (stream) {
        stream.getTracks().forEach(t => t.stop());
    }
    
    if (state.liveSocket) {
        try {
            state.liveSocket.close();
        } catch(e){}
        state.liveSocket = null;
    }
    
    state.liveMediaRecorder = null;
}

function startLiveChunkRecorder(stream, chunkSizeSec) {
    if (state.liveStopping || !state.liveSocket || state.liveSocket.readyState !== WebSocket.OPEN) return;

    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    state.liveMediaRecorder = recorder;

    recorder.ondataavailable = async (e) => {
        if (e.data && e.data.size > 0 && state.liveSocket && state.liveSocket.readyState === WebSocket.OPEN) {
            const arrayBuffer = await e.data.arrayBuffer();
            state.liveSocket.send(arrayBuffer);
        }
    };

    recorder.onstop = () => {
        if (!state.liveStopping && state.liveSocket && state.liveSocket.readyState === WebSocket.OPEN) {
            startLiveChunkRecorder(stream, chunkSizeSec);
        }
    };

    recorder.start();
    state.liveChunkTimer = setTimeout(() => {
        if (recorder.state !== "inactive") {
            recorder.stop();
        }
    }, chunkSizeSec * 1000);
}

// --- DICIONÁRIO DE AJUDA DETALHADA E LOGICA DO MODAL ---
const helpTopics = {
    engine: {
        title: "Motor de IA (Engine)",
        content: `
            <p>Selecione a engine de transcrição que processará o seu áudio:</p>
            <ul>
                <li><strong>Whisper (Padrão):</strong> Desenvolvido pela OpenAI, é extremamente rápido no processamento na GPU CUDA e altamente preciso para texto contínuo. Não faz diarização de falantes nativamente nesta versão rápida.</li>
                <li><strong>VibeVoice ASR:</strong> Modelo otimizado para tarefas de transcrição e <strong>diarização (separação de vozes/falantes)</strong>. Requer mais recursos de computação do que o Whisper.</li>
            </ul>
        `
    },
    whisper_model: {
        title: "Modelo do Whisper",
        content: `
            <p>Define o tamanho do modelo neural utilizado para a transcrição:</p>
            <ul>
                <li><strong>Tiny / Base / Small:</strong> Modelos super velozes com baixo consumo de memória. Ideais para testes rápidos ou hardware com pouca VRAM.</li>
                <li><strong>Medium:</strong> Ótimo equilíbrio para português (PT-BR) com alta precisão e velocidade moderada.</li>
                <li><strong>Large V3 Turbo (Recomendado):</strong> Modelo otimizado de 800M de parâmetros. Oferece a melhor precisão e velocidade usando os núcleos Tensor da sua RTX 3050.</li>
                <li><strong>Large V3:</strong> O modelo mais completo (1.5B parâmetros). Máxima acurácia, porém mais lento e com maior consumo de VRAM.</li>
            </ul>
        `
    },
    device: {
        title: "Dispositivo de Processamento",
        content: `
            <p>Escolhe em qual hardware o modelo será executado:</p>
            <ul>
                <li><strong>CUDA (GPU RTX 3050):</strong> Processamento por placa de vídeo dedicada. É até 20x mais rápido que a CPU, ideal para áudios longos.</li>
                <li><strong>CPU:</strong> Executa no seu processador i7-13650HX. Mais lento, mas útil caso a placa de vídeo esteja sobrecarregada ou sem VRAM livre.</li>
            </ul>
        `
    },
    compute_type: {
        title: "Tipo de Precisão (Quantização)",
        content: `
            <p>Controla a precisão matemática dos pesos do modelo para economizar VRAM e acelerar o processamento:</p>
            <ul>
                <li><strong>Float16 (Padrão):</strong> Recomendado para GPUs NVIDIA. Oferece alta velocidade de processamento sem perda perceptível de qualidade.</li>
                <li><strong>Int8 Float16 / Int8:</strong> Comprime os pesos matemáticos do modelo em 8 bits. Reduz quase pela metade o uso de memória (VRAM/RAM), permitindo rodar modelos maiores.</li>
                <li><strong>Float32:</strong> Precisão total original do modelo. Consome o dobro de memória e é significativamente mais lento.</li>
            </ul>
        `
    },
    beam_size: {
        title: "Tamanho de Busca (Beam Size)",
        content: `
            <p>Quantidade de hipóteses textuais que o algoritmo avalia em paralelo a cada palavra decodificada:</p>
            <ul>
                <li><strong>Valores Baixos (1 a 3):</strong> Transcrição extremamente rápida, porém com chances levemente maiores de cometer pequenos deslizes em trechos ruidosos.</li>
                <li><strong>Valor Padrão (5):</strong> O equilíbrio ideal para sessões clínicas, garantindo precisão em termos técnicos sem lentidão.</li>
                <li><strong>Valores Altos (6 a 10):</strong> Busca exaustiva. Melhora a qualidade de áudios com sussurros ou muito ruído, mas aumenta o tempo de processamento.</li>
            </ul>
        `
    },
    vad_filter: {
        title: "Filtro de Silêncio (VAD)",
        content: `
            <p><strong>Voice Activity Detection (Detecção de Atividade de Voz):</strong></p>
            <p>Quando ativado, o sistema remove todos os trechos de silêncio absoluto antes de enviar o áudio ao Whisper.</p>
            <ul>
                <li><strong>Recomendação (Ativado):</strong> Evita alucinações onde o modelo se perde repetindo a mesma palavra infinitamente em períodos de silêncio prolongados da gravação.</li>
            </ul>
        `
    },
    cpu_threads: {
        title: "Threads de CPU",
        content: `
            <p>Quantidade de núcleos lógicos do processador dedicados a decodificar o áudio em PCM:</p>
            <ul>
                <li><strong>Recomendação (Padrão: 8):</strong> O seu i7 possui 14 núcleos físicos (20 threads lógicos). Definir como 8 ou 12 oferece performance máxima sem congelar o seu Windows.</li>
            </ul>
        `
    },
    whisper_language: {
        title: "Idioma do Whisper",
        content: `
            <p>Força o Whisper a decodificar o áudio no idioma selecionado:</p>
            <ul>
                <li><strong>Detectar Automaticamente:</strong> O modelo ouve os primeiros 30 segundos e decide o idioma da transcrição.</li>
                <li><strong>Português (Brasil) / Inglês / Espanhol:</strong> Útil para evitar que palavras com sotaques mistos façam o Whisper traduzir ou transcrever em outro idioma por engano.</li>
            </ul>
        `
    },
    whisper_temperature: {
        title: "Temperatura (Whisper)",
        content: `
            <p>Controla o grau de criatividade e aleatoriedade durante a geração:</p>
            <ul>
                <li><strong>0.0 (Padrão/Determinístico):</strong> A IA sempre escolherá a palavra mais provável, gerando transcrições precisas e consistentes.</li>
                <li><strong>Valores maiores (0.1 a 1.0):</strong> Adiciona aleatoriedade. Útil em sessões altamente ruidosas se o modelo travar em loops, mas aumenta o risco de inventar palavras.</li>
            </ul>
        `
    },
    whisper_prompt: {
        title: "Termos Customizados (Whisper)",
        content: `
            <p>Guia de estilo e grafia para termos específicos:</p>
            <p>Insira termos do assunto, siglas específicas ou nomes de pessoas separados por vírgula. O Whisper lerá esse guia no início e tentará usar essa grafia correta em vez de tentar adivinhar a ortografia.</p>
        `
    },
    vibevoice_prompt: {
        title: "Termos Customizados (VibeVoice)",
        content: `
            <p>Funciona de forma similar ao Whisper. O VibeVoice priorizará as palavras inseridas neste campo ao decodificar os fonemas do áudio, melhorando o reconhecimento de abreviações e jargões do assunto ou área de atuação.</p>
        `
    },
    vibevoice_diarization: {
        title: "Diarização de Falantes",
        content: `
            <p>Identificação de interlocutores no áudio:</p>
            <p>Analisa as características de frequência vocal para identificar as vozes e rotulá-las dinamicamente como <i>(Falante 1)</i>, <i>(Falante 2)</i>, etc.</p>
            <ul>
                <li><strong>Recomendação (Ativado):</strong> Essencial para separar no texto o que foi dito por cada um dos interlocutores ou palestrantes.</li>
            </ul>
        `
    },
    vibevoice_chunk_size: {
        title: "Janela Interna do Tokenizer (VibeVoice)",
        content: `
            <p>Controla a janela interna usada pelo tokenizer acústico do VibeVoice durante uma transcrição em passagem única:</p>
            <ul>
                <li><strong>Padrão: 60 segundos.</strong></li>
                <li>Valores menores reduzem picos de memória. O áudio não é quebrado em transcrições separadas; o modelo mantém a diarização e o contexto global.</li>
            </ul>
        `
    },
    vibevoice_temperature: {
        title: "Temperatura (VibeVoice)",
        content: `
            <p>Controla a aleatoriedade de geração do VibeVoice. Mantê-la em <strong>0.0</strong> garante que o modelo escolha a melhor combinação fonética estrutural sem criar alucinações.</p>
        `
    },
    vibevoice_repetition_penalty: {
        title: "Penalidade de Repetição",
        content: `
            <p>Penaliza o modelo se ele tentar repetir palavras repetidamente na mesma frase:</p>
            <ul>
                <li><strong>Padrão: 1.1.</strong></li>
                <li>Valores como 1.1 ou 1.2 são recomendados para evitar que a IA entre em loops infinitos gerando gagueiras ou ruídos repetitivos.</li>
            </ul>
        `
    },
    vibevoice_top_p: {
        title: "Top-P (Nucleus Sampling)",
        content: `
            <p>Amostragem cumulativa de probabilidade:</p>
            <ul>
                <li><strong>Padrão: 1.0 (Desativado).</strong></li>
                <li>Se definido abaixo de 1.0 (ex: 0.9), a IA considerará apenas o menor conjunto de palavras mais prováveis cuja soma das probabilidades atinja P. Útil para refinar a geração se a temperatura for maior que 0.0.</li>
            </ul>
        `
    },
    vibevoice_top_k: {
        title: "Top-K",
        content: `
            <p>Limita o número de escolhas possíveis de palavras a cada passo de geração:</p>
            <ul>
                <li><strong>Padrão: 50.</strong></li>
                <li>Mantém as opções filtradas entre os 50 tokens mais relevantes no vocabulário neural.</li>
            </ul>
        `
    },
    vibevoice_num_beams: {
        title: "Busca por Feixe (Num Beams)",
        content: `
            <p>Número de feixes de busca paralelos explorados para otimização gramatical:</p>
            <ul>
                <li><strong>Padrão: 1 (Rápido / Modo Streamer).</strong></li>
                <li>Ao definir como 1, o sistema exibe os tokens de texto sendo digitados na tela em tempo real à medida que são previstos pelo modelo.</li>
                <li><strong>Beams maiores que 1:</strong> Aumentam a acurácia gramatical avaliando múltiplos caminhos, mas <strong>desativam o streaming de texto em tempo real por fatia</strong> (os blocos de texto só aparecem na tela quando a fatia for completamente decodificada).</li>
            </ul>
        `
    },
    vibevoice_max_new_tokens: {
        title: "Limite de Tokens (Fatia)",
        content: `
            <p>Tamanho máximo de texto gerado para cada fatia de áudio (2048 tokens equivalem a aproximadamente 1500 palavras):</p>
            <ul>
                <li>Garante que mesmo fatias longas de áudio com falas contínuas e rápidas não tenham seu texto cortado pela metade durante o processamento.</li>
            </ul>
        `
    },
    live_chunk_size: {
        title: "Tamanho do Trecho (Tempo Real)",
        content: `
            <p>Define o intervalo de transmissão (em segundos) para o envio de trechos de áudio gravados pelo microfone na modalidade de Transmissão Ao Vivo:</p>
            <ul>
                <li><strong>Recomendado: 5 segundos.</strong></li>
                <li>Trechos muito curtos (ex: 2s) dão respostas super rápidas, mas podem cortar palavras no meio. Trechos mais longos (ex: 8s) garantem excelente concordância contextual.</li>
            </ul>
        `
    },
    tts_model: {
        title: "Modelo de Síntese (TTS)",
        content: `
            <p>Selecione o motor neural para geração de voz:</p>
            <ul>
                <li><strong>VibeVoice-TTS-1.5B:</strong> modelo oficial de longa duração listado na coleção da Microsoft. É a opção padrão para textos longos e diálogos multi-falante.</li>
                <li><strong>VibeVoice-Large:</strong> variante maior disponível em aoi-ot/VibeVoice-Large. É mais pesada, tem cerca de 18,7 GB e exige a biblioteca local VibeVoice para inferência.</li>
                <li><strong>VibeVoice-Realtime-0.5B:</strong> modelo de um falante voltado a baixa latência e respostas curtas. A aba de chat usa este modo automaticamente.</li>
            </ul>
        `
    },
    tts_speaker: {
        title: "Voz / Locutor Padrão",
        content: `
            <p>Define a assinatura vocal base para a síntese:</p>
            <p>O VibeVoice possui vozes integradas calibradas para português e inglês. As vozes ímpares (Voz 1 e 3) apresentam tons masculinos mais firmes e dinâmicos, ideais para narração ou apresentações comerciais. As vozes pares (Voz 2 e 4) possuem tons femininos com cadência natural, adequados para explicações detalhadas e suporte.</p>
        `
    },
    tts_temperature: {
        title: "Temperatura (TTS)",
        content: `
            <p>Controla a expressividade e variação tonal da voz sintetizada:</p>
            <ul>
                <li><strong>Valores baixos (0.1 a 0.5):</strong> Tom de voz muito estável e previsível, mas pode soar monótono.</li>
                <li><strong>Valores médios (0.6 a 0.8 - Recomendado):</strong> Equilíbrio excelente entre naturalidade, prosódia e expressividade.</li>
                <li><strong>Valores altos (0.9 a 1.2):</strong> Tom de voz bastante expressivo e dinâmico, mas pode gaguejar ou oscilar em ruído fonético.</li>
            </ul>
        `
    },
    tts_speed: {
        title: "Velocidade da Fala",
        content: `
            <p>Controla a velocidade do fluxo de leitura do texto:</p>
            <ul>
                <li><strong>Padrão: 1.0x.</strong></li>
                <li>Ajuste entre <strong>0.5x</strong> (leitura lenta/didática) até <strong>2.0x</strong> (leitura ultra rápida) sem causar distorção metálica no tom da voz devido à modulação do vocoder neural.</li>
            </ul>
        `
    },
    tts_repetition_penalty: {
        title: "Penalidade de Repetição (TTS)",
        content: `
            <p>Evita que o sintetizador neural entre em loops fonéticos ou repetições de sílabas:</p>
            <ul>
                <li><strong>Padrão: 1.1.</strong></li>
                <li>Garante clareza e impede que o sintetizador trave repetindo sons sibilantes ou gaguejando ao processar pontuações raras.</li>
            </ul>
        `
    }
};

function setupInfoModal() {
    const modal = document.getElementById("info-modal");
    const modalTitle = document.getElementById("modal-title");
    const modalBody = document.getElementById("modal-body-content");
    const closeBtn = document.getElementById("modal-close-btn");

    // Delegação de evento de clique para os botões .info-btn
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".info-btn");
        if (btn) {
            const topicKey = btn.getAttribute("data-info");
            const topic = helpTopics[topicKey];
            if (topic) {
                modalTitle.textContent = topic.title;
                modalBody.innerHTML = topic.content;
                modal.style.display = "flex";
            }
        }
    });

    // Fecha ao clicar no botão X
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            modal.style.display = "none";
        });
    }

    // Fecha ao clicar fora do modal-content
    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.style.display = "none";
        }
    });
}
