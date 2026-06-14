// Setup Wizard - primeiro uso
(function () {
    let wizardModal = null;
    let currentStep = 1;

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
        else console.log("[wizard]", message);
    }

    async function checkSetup() {
        try {
            const status = await fetchJSON("/api/setup/status");
            if (!status.first_run_completed) {
                showWizard(status);
            }
        } catch (error) {
            console.error("Falha ao checar setup:", error);
        }
    }

    function showWizard(status) {
        if (document.getElementById("setup-wizard-modal")) return;

        wizardModal = document.createElement("div");
        wizardModal.id = "setup-wizard-modal";
        wizardModal.className = "modal-overlay";
        wizardModal.style.display = "flex";
        wizardModal.style.zIndex = "2000";

        document.body.appendChild(wizardModal);
        renderStep(status);
    }

    function renderStep(status) {
        let content = "";
        const stepsCount = 6;

        if (currentStep === 1) {
            content = `
                <h2>✍️ Bem-vindo ao EscribaLocal!</h2>
                <p>Esta é a sua central local de Transcrição e Geração de Voz de alta performance.</p>
                <p>Vamos configurar o seu ambiente em poucos passos para garantir a melhor estabilidade e desempenho possível.</p>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:flex-end;">
                    <button class="model-btn model-btn-primary" id="wizard-next">Avançar ➔</button>
                </div>
            `;
        } else if (currentStep === 2) {
            content = `
                <h2>🔍 Diagnóstico de Ambiente</h2>
                <p>Verificando o hardware e os pacotes necessários para rodar os modelos locais.</p>
                <div id="wizard-env-loading" class="model-notes">Analisando o sistema...</div>
                <div id="wizard-env-results" style="max-height: 250px; overflow-y: auto; margin: 15px 0;"></div>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:space-between; align-items:center;">
                    <button class="model-btn" id="wizard-prev">⬅ Voltar</button>
                    <button class="model-btn model-btn-primary" id="wizard-next" disabled>Avançar ➔</button>
                </div>
            `;
        } else if (currentStep === 3) {
            content = `
                <h2>🧩 Catálogo de Modelos</h2>
                <p>Estes são os modelos de IA disponíveis para download. O ideal para iniciar rapidamente é o Whisper <b>small</b>.</p>
                <div id="wizard-models-results" style="max-height: 250px; overflow-y: auto; margin: 15px 0;">
                    Carregando catálogo do Hugging Face...
                </div>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:space-between;">
                    <button class="model-btn" id="wizard-prev">⬅ Voltar</button>
                    <button class="model-btn model-btn-primary" id="wizard-next">Avançar ➔</button>
                </div>
            `;
        } else if (currentStep === 4) {
            content = `
                <h2>🎛 Configuração de Preset</h2>
                <p>O EscribaLocal analisou seu computador e sugeriu uma configuração inicial conservadora para garantir estabilidade:</p>
                <div style="background:rgba(255,255,255,0.02); padding:15px; border-radius:8px; border:1px solid var(--border-color); margin:15px 0;">
                    <h4 style="margin:0 0 5px 0; color:var(--accent-cyan);">Preset sugerido: ${status.suggested_preset === "baixa-memoria" ? "Baixa memória (Recomendado)" : "Seguro (CPU)"}</h4>
                    <p style="margin:0; font-size:12px; line-height:1.4;">Preset conservador focado em estabilidade de VRAM. Você pode rodar benchmarks e mudar essa configuração a qualquer momento na sidebar lateral.</p>
                </div>
                <div style="display:flex; gap:10px; align-items:center; margin-top:10px;">
                    <button class="model-btn model-btn-primary" id="wizard-apply-preset">Aplicar Preset Sugerido</button>
                    <span id="wizard-preset-status" class="model-notes"></span>
                </div>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:space-between;">
                    <button class="model-btn" id="wizard-prev">⬅ Voltar</button>
                    <button class="model-btn model-btn-primary" id="wizard-next">Avançar ➔</button>
                </div>
            `;
        } else if (currentStep === 5) {
            const retEnabled = status.retention.enabled;
            content = `
                <h2>💾 Retenção de Uploads & Reexecução (Retry)</h2>
                <p>Para permitir a reexecução de transcrições com parâmetros diferentes sem precisar reenviar o áudio, os uploads são retidos temporariamente no servidor local.</p>
                <div style="background:rgba(0,242,254,0.05); border:1px solid rgba(0,242,254,0.2); padding:15px; border-radius:8px; margin:15px 0;">
                    <p style="margin:0 0 8px 0; font-size:13px;"><b>Privacidade & Armazenamento Local:</b></p>
                    <ul style="margin:0; padding-left:20px; font-size:12.5px; line-height:1.5;">
                        <li>Os arquivos de áudio permanecem exclusivamente no seu computador.</li>
                        <li>Retenção atual: <b>${retEnabled ? `Ativada (Limite máximo: ${status.retention.max_mb} MB)` : "Desativada (Deletado imediatamente)"}</b>.</li>
                        <li>Os arquivos são excluídos automaticamente quando o limite é atingido ou expirados por tempo (TTL).</li>
                    </ul>
                </div>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:space-between;">
                    <button class="model-btn" id="wizard-prev">⬅ Voltar</button>
                    <button class="model-btn model-btn-primary" id="wizard-next">Avançar ➔</button>
                </div>
            `;
        } else if (currentStep === 6) {
            content = `
                <h2>🎉 Tudo Pronto!</h2>
                <p>A configuração inicial do EscribaLocal foi concluída.</p>
                <p>Clique em <b>Concluir</b> para fechar este assistente e começar a transcrever ou sintetizar voz.</p>
                <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:space-between;">
                    <button class="model-btn" id="wizard-prev">⬅ Voltar</button>
                    <button class="model-btn model-btn-primary" id="wizard-finish">Concluir ✔</button>
                </div>
            `;
        }

        wizardModal.innerHTML = `
            <div class="modal-content" style="max-width:550px; padding:30px; position:relative;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border-color); padding-bottom:10px;">
                    <span style="font-weight:600; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">Assistente de Configuração</span>
                    <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">${currentStep} de ${stepsCount}</span>
                </div>
                <div class="wizard-step-body">${content}</div>
            </div>
        `;

        // Bind events
        const nextBtn = document.getElementById("wizard-next");
        const prevBtn = document.getElementById("wizard-prev");
        const finishBtn = document.getElementById("wizard-finish");
        const applyPresetBtn = document.getElementById("wizard-apply-preset");

        if (nextBtn) {
            nextBtn.addEventListener("click", () => {
                currentStep++;
                renderStep(status);
            });
        }
        if (prevBtn) {
            prevBtn.addEventListener("click", () => {
                currentStep--;
                renderStep(status);
            });
        }
        if (finishBtn) {
            finishBtn.addEventListener("click", completeSetup);
        }
        if (applyPresetBtn) {
            applyPresetBtn.addEventListener("click", () => applyPreset(status.suggested_preset));
        }

        // Executar ações de passos específicos
        if (currentStep === 2) {
            runEnvironmentChecks();
        } else if (currentStep === 3) {
            loadModelsForWizard();
        }
    }

    async function runEnvironmentChecks() {
        const loading = document.getElementById("wizard-env-loading");
        const results = document.getElementById("wizard-env-results");
        const nextBtn = document.getElementById("wizard-next");

        try {
            const data = await fetchJSON("/api/environment");
            if (loading) loading.style.display = "none";
            
            const checks = data.checks || [];
            results.innerHTML = checks.map(c => {
                let badge = "";
                if (c.status === "ok") badge = `<span class="model-badge model-badge-ok">OK</span>`;
                else if (c.status === "warn") badge = `<span class="model-badge model-badge-warn">Aviso</span>`;
                else badge = `<span class="model-badge model-badge-busy" style="background:var(--accent-danger);">Falha</span>`;
                
                return `
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.03); font-size:13px;">
                        <span><b>${c.name}</b>: <small style="color:var(--text-muted);">${c.detail}</small></span>
                        ${badge}
                    </div>
                `;
            }).join("");

            if (nextBtn) nextBtn.disabled = false;
        } catch (error) {
            if (loading) loading.textContent = "Erro ao diagnosticar ambiente: " + error.message;
        }
    }

    async function loadModelsForWizard() {
        const container = document.getElementById("wizard-models-results");
        try {
            const data = await fetchJSON("/api/models");
            const models = data.models || [];
            
            const whisperSmall = models.find(m => m.id === "whisper-small");
            if (!whisperSmall) {
                container.textContent = "Modelo Whisper small não localizado no catálogo.";
                return;
            }

            container.innerHTML = `
                <div style="background:rgba(255,255,255,0.01); border:1px solid var(--border-color); padding:15px; border-radius:8px; display:flex; flex-direction:column; gap:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>${whisperSmall.display_name}</strong>
                        <span class="model-badge">${whisperSmall.installed ? "Instalado" : "Não instalado"}</span>
                    </div>
                    <p style="margin:0; font-size:12px; color:var(--text-muted);">${whisperSmall.notes}</p>
                    <div style="display:flex; gap:10px; align-items:center; margin-top:5px;">
                        <button class="model-btn model-btn-primary" id="wizard-dl-btn" ${whisperSmall.installed ? "disabled" : ""}>
                            ${whisperSmall.installed ? "Modelo já instalado" : "⬇️ Baixar Whisper Small"}
                        </button>
                        <span id="wizard-dl-status" class="model-notes"></span>
                    </div>
                </div>
            `;

            const dlBtn = document.getElementById("wizard-dl-btn");
            if (dlBtn && !whisperSmall.installed) {
                dlBtn.addEventListener("click", () => startDownloadFromWizard(whisperSmall.id));
            }
        } catch (error) {
            container.textContent = "Erro ao carregar catálogo: " + error.message;
        }
    }

    async function startDownloadFromWizard(modelId) {
        const dlBtn = document.getElementById("wizard-dl-btn");
        const dlStatus = document.getElementById("wizard-dl-status");
        if (dlBtn) dlBtn.disabled = true;

        try {
            const data = await fetchJSON("/api/models/download", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: modelId }),
            });

            const eventSource = new EventSource(`/api/jobs/${data.job_id}/events`);
            eventSource.onmessage = (message) => {
                let event;
                try { event = JSON.parse(message.data); } catch (e) { return; }

                if (event.type === "download_progress") {
                    if (dlStatus) dlStatus.textContent = `Progresso: ${event.percent}% @ ${event.speed_mb} MB/s`;
                } else if (event.type === "job_state") {
                    if (event.state === "completed") {
                        if (dlStatus) dlStatus.textContent = "Download concluído!";
                        eventSource.close();
                        toast("Download concluído.");
                    } else if (["failed", "cancelled"].includes(event.state)) {
                        if (dlStatus) dlStatus.textContent = `Falhou: ${event.error || "cancelado"}`;
                        if (dlBtn) dlBtn.disabled = false;
                        eventSource.close();
                    }
                }
            };
        } catch (error) {
            toast(`Falha no download: ${error.message}`, true);
            if (dlBtn) dlBtn.disabled = false;
        }
    }

    async function applyPreset(presetId) {
        const btn = document.getElementById("wizard-apply-preset");
        const statusSpan = document.getElementById("wizard-preset-status");
        if (btn) btn.disabled = true;

        try {
            const result = await fetchJSON(`/api/presets/${presetId}/apply`, { method: "POST" });
            if (window.applyParamsToForm && result.form_params) {
                window.applyParamsToForm(result.form_params);
            }
            if (statusSpan) statusSpan.innerHTML = "✓ Preset aplicado com sucesso!";
            toast("Preset sugerido aplicado.");
        } catch (error) {
            if (statusSpan) statusSpan.textContent = "Falha ao aplicar preset: " + error.message;
            if (btn) btn.disabled = false;
        }
    }

    async function completeSetup() {
        try {
            await fetchJSON("/api/setup/complete", { method: "POST" });
            if (wizardModal) {
                wizardModal.remove();
            }
            toast("Bem-vindo! Configuração concluída.");
        } catch (error) {
            toast("Falha ao concluir setup: " + error.message, true);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        checkSetup();
    });
})();
