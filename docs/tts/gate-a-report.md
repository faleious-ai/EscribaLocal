# Gate A - Relatorio de execucao

Data: 2026-06-16

Branch: `codex/tts-gate-a`

PR: #15 draft

Commit-base: `b342721c34d883bf9769a3f6c066188b4e29f2a4`

HEAD antes desta rodada de revisao: `b75ed41bf08fcedc618d45cc8f3bbba3f8d335c6`

Commit final: ver o commit que contem este pacote na branch
`codex/tts-gate-a`; o hash exato deve ser conferido no resumo final da rodada.

Fonte de verdade: `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`

Ledger: `docs/tts/EXECUTION_STATUS.md`

## Objetivo do Gate A

Restaurar confianca no subsistema TTS removendo caminhos funcionais de audio
falso ou identidade falsa: presets Windows, SAPI5, senoide, smoke sintetico,
fallback de engine e Large com referencia artificial.

## Implementado

- T0.1: baseline auditavel registrado em `docs/tts/gate-a-baseline.md`.
- T0.2: escopo atual registrado em `docs/tts/`; `CONTEXT.md` agora exige leitura conjunta de escopo, ledger e relatorio do gate atual.
- T1.1: presets Windows e aliases `speaker_1..4` usados como identidade vocal nao resolvem voz real. `is_preset()` foi removido; callers usam rejeicao explicita de ID legado.
- T1.1: migracao idempotente limpa ou migra selecoes antigas em `config/settings.json`, perfis em `config/profiles/*.json` e `localStorage` da biblioteca de vozes.
- T1.2: runtime/adapters/scripts nao usam SAPI5, senoide ou smoke sintetico como saida de producao.
- T1.3: teste global de caminhos proibidos usa `PROJECT_ROOT = Path(__file__).resolve().parents[1]`, funciona fora da raiz e restringe a varredura a arquivos funcionais.
- T1.3: matriz de engine mismatch exige `engine_key` explicita, igualdade entre engine solicitada e executada, e `fallback=false`.
- T9.3: VibeVoice Large permanece bloqueado sem referencias reais por speaker.
- T10.1: Realtime 0.5B rejeita sucesso do worker sem `engine_key` e segue indisponivel sem PCM/WAV nativo real validado.

## Validado nesta rodada

- `python -m pytest`: `217 passed`, `2 warnings` de `FastAPI.on_event`.
- `python -m pytest tests/test_tts_legacy_voice_migration.py`: `5 passed`.
- `python -m pytest tests/test_tts_no_fallbacks.py`: `13 passed`, `2 warnings` de `FastAPI.on_event`.
- `python -m pytest tests/test_tts_forbidden_runtime_paths.py`: `1 passed`.
- `python -m pytest <repo>/tests/test_tts_forbidden_runtime_paths.py` iniciado fora da raiz: `1 passed`.
- `python -m pytest tests/test_tts_realtime_worker.py`: `21 passed`, `2 warnings` de `FastAPI.on_event`.
- `python -m pytest tests/test_tts_large_clear_errors.py`: `5 passed`, `2 warnings` de `FastAPI.on_event`.
- `python -m pytest tests/test_voice_profiles.py`: `23 passed`, `2 warnings` de `FastAPI.on_event`.
- `python -m compileall main.py routers services workers scripts tests`: sucesso.
- `python -c "import main; ..."`: sucesso.
- `git diff --check`: sem erro; apenas avisos esperados de CRLF no Windows.

## Busca estatica e classificacao

Busca ampla executada:

```powershell
rg -n "SAPI|win32com|pyttsx3|System\.Speech|SpVoice|preset_windows|PRESET_VOICES|math\.sin|np\.sin|synthetic_smoke|fallback|speaker_[1-4]" main.py services workers routers static scripts tests docs/tts
```

Classificacao:

- Funcional proibido: nenhuma ocorrencia.
- Documentacao: `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`, `docs/tts/gate-a-baseline.md`, este relatorio, `TRACKER_UPDATE_PROPOSAL.md` e `gate-a-review-package.md`.
- Compatibilidade rejeitora: mensagens em `main.py`, `services/vibevoice_tts_1_5b.py`, `services/parameters_registry.py`, `routers/voice_routes.py`, `services/model_manager.py`, `services/presets.py`.
- Migracao/rejeicao de legado: `services/config_store.py`, `services/voice_profiles.py`, `static/js/voice_library.js`.
- Metadados permitidos sem audio falso: campos `fallback=false` em `workers/vibevoice_realtime_worker.py`, `services/vibevoice_realtime_0_5b.py`, `services/vibevoice_service.py`, `services/chatterbox_adapter.py`, `services/vibevoice_tts_1_5b.py` e status visual em `static/app.js`, `static/index.html`, `static/style.css`.
- Testes negativos: `tests/test_tts_no_fallbacks.py`, `tests/test_tts_realtime_worker.py`, `tests/test_tts_real_voices_required.py`, `tests/test_voice_profiles.py`, `tests/test_tts_legacy_voice_migration.py`.
- Falsos positivos fora de TTS proibido: fallback de NVML/hardware/transcricao em `services/hardware.py`, `services/transcriber.py`, `tests/test_hardware.py`.

Busca funcional proibida executada:

```powershell
rg -n "win32com|pyttsx3|System\.Speech|SpVoice|PRESET_VOICES|PRESET_IDS|math\.sin|np\.sin|_write_sine|_synthetic_smoke_(enabled|response|pcm_bytes)|synthetic_smoke_enabled" main.py services workers routers static scripts
```

Resultado: sem ocorrencias.

Busca Large/Realtime removidos:

```powershell
rg -n "_build_voice_samples|_create_voice_prompt_wav|_write_sine_voice_prompt|synthetic_smoke_enabled|_synthetic_smoke" services workers scripts main.py static
```

Resultado: sem ocorrencias.

## Bloqueado

Nada bloqueado no Gate A ate o momento. O Large e o Realtime seguem
indisponiveis por decisao de escopo, nao por bloqueio de implementacao do Gate A.

## Movido para Gate B ou posterior

- Criacao/importacao automatica da primeira voz real: Gate B, T2.1-T2.3.
- Versionamento completo de `profile.json`: Gate B, T2.1.
- Estilos persistidos, tags novas, parser de roteiro e RenderPlan: Gates B/C.
- Chatterbox multi-voz por segmento e parametros dinamicos completos: Gates D/E.
- Realtime 0.5B nativo em subprocesso: Gate F, T10.2/T10.3.

## Migração legada

Regras implementadas:

- `preset_windows_1..4` e `speaker_1..4` sao tratados como IDs legados quando aparecem em campos de identidade vocal.
- Se houver uma unica voz real inequivoca, a selecao legada passa para essa voz real.
- Se nao houver escolha inequivoca, a selecao e limpa e o TTS permanece pendente/desabilitado ate o usuario criar, importar ou selecionar voz real.
- Voz real valida e preservada.
- ID inexistente e limpo.
- A segunda execucao da migracao nao altera novamente o arquivo.
- Nenhuma voz real em `data/voices` e apagada.

Cobertura adicionada:

- config com `preset_windows_1`;
- config com `speaker_1`;
- voz real valida;
- ausencia de voz;
- ID inexistente;
- `localStorage` antigo;
- primeira execucao pos-update;
- segunda execucao pos-migracao.

## Ambiente

- SO: Windows.
- Python: 3.12.10 observado nas execucoes de pytest.
- Warnings conhecidos: `FastAPI.on_event` deprecated, ja existentes e fora do escopo do Gate A.

## Arquivos alterados nesta rodada

- `CONTEXT.md`
- `docs/tts/EXECUTION_STATUS.md`
- `docs/tts/gate-a-report.md`
- `docs/tts/TRACKER_UPDATE_PROPOSAL.md`
- `docs/tts/gate-a-review-package.md`
- `main.py`
- `services/config_store.py`
- `services/voice_profiles.py`
- `services/vibevoice_tts_1_5b.py`
- `services/chatterbox_adapter.py`
- `services/vibevoice_realtime_0_5b.py`
- `static/js/voice_library.js`
- `tests/test_tts_legacy_voice_migration.py`
- `tests/test_tts_no_fallbacks.py`
- `tests/test_tts_forbidden_runtime_paths.py`
- `tests/test_tts_realtime_worker.py`
- `tests/test_tts_orchestration.py`

## Proximo gate permitido

Somente apos revisao externa do Gate A: iniciar Gate B por T2.1. Nao iniciar
parser, RenderPlan, estilos ou Realtime nativo nesta branch enquanto Gate A
estiver em revisao.
