# Gate A - Pacote de revisao

Data: 2026-06-16

Branch: `codex/tts-gate-a`

PR: #15 draft

Base: `b342721c34d883bf9769a3f6c066188b4e29f2a4`

HEAD antes desta rodada: `b75ed41bf08fcedc618d45cc8f3bbba3f8d335c6`

Commit final: ver o commit que contem este pacote na branch
`codex/tts-gate-a`; o hash exato deve ser conferido no resumo final da rodada.

## Resumo

Esta rodada verificou os achados do Gate A contra o codigo atual e implementou
somente correcoes do Gate A:

- migracao idempotente de selecoes legadas de voz;
- remocao definitiva da funcao `is_preset()`;
- rejeicao explicita de IDs legados `preset_windows_1..4` e `speaker_1..4` quando usados como identidade vocal;
- `localStorage` antigo saneado na biblioteca de vozes;
- validacao pura de engine executada, exigindo `engine_key` explicita;
- Realtime rejeitando sucesso de worker sem `engine_key`;
- teste global de caminhos proibidos independente do diretorio atual;
- ledger e proposta de tracker criados.

Gate B nao foi iniciado.

## Decisoes preservadas

- Uma solicitacao usa uma engine ou falha explicitamente.
- `engine_key` ausente em sucesso e erro, nao evidencia de sucesso.
- Nenhum fallback de engine, voz ou audio e aceito.
- Presets Windows, SAPI5, senoide e smoke sintetico nao sao caminhos validos de producao.
- Large so pode executar com referencias reais.
- Realtime 0.5B so pode ficar disponivel depois de PCM/WAV nativo real em worker isolado.
- A PRD antiga e historica e nao limita o escopo atual.

## Arquivos alterados

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

## Migracao

Backend:

- `config/settings.json`, `config/profiles/*.json` e secoes `defaults.tts`,
  `engine_params.tts` ou `tts` sao migradas ao carregar.
- Campos de identidade vocal cobertos: `voice_id`, `default_voice_id`,
  `selected_voice_id`, `identity_voice_id`.
- Mapas cobertos: `speaker_voices`, `speaker_voice_map`.
- IDs legados cobertos: `preset_windows_1..4`, `speaker_1..4`.
- Se ha exatamente uma voz real default, ou exatamente uma voz real total, a
  selecao legada usa essa voz.
- Se nao ha escolha unica, a selecao e limpa.
- IDs reais existentes sao preservados.
- IDs inexistentes sao limpos.
- Segunda execucao nao altera o resultado.

Frontend:

- `static/js/voice_library.js` limpa ou migra `escriba_tts_voice_settings` apos carregar `/api/tts/voices`.
- O envio de `voice_id` e `speaker_voices` ignora IDs legados.

## Testes

Executados:

- `python -m pytest` -> `217 passed`, `2 warnings`
- `python -m pytest tests/test_tts_legacy_voice_migration.py` -> `5 passed`
- `python -m pytest tests/test_tts_no_fallbacks.py` -> `13 passed`, `2 warnings`
- `python -m pytest tests/test_tts_forbidden_runtime_paths.py` -> `1 passed`
- `python -m pytest <repo>/tests/test_tts_forbidden_runtime_paths.py` iniciado fora da raiz -> `1 passed`
- `python -m pytest tests/test_tts_realtime_worker.py` -> `21 passed`, `2 warnings`
- `python -m pytest tests/test_tts_large_clear_errors.py` -> `5 passed`, `2 warnings`
- `python -m pytest tests/test_voice_profiles.py` -> `23 passed`, `2 warnings`
- `python -m compileall main.py routers services workers scripts tests` -> sucesso
- `python -c "import main; ..."` -> sucesso
- `git diff --check` -> sem erro; apenas avisos esperados de CRLF no Windows

## Evidencias

- `tests/test_tts_legacy_voice_migration.py` cobre config com `preset_windows_1`,
  config com `speaker_1`, voz real valida, sem voz, ID inexistente,
  `localStorage` antigo, primeira execucao e segunda execucao.
- `tests/test_tts_no_fallbacks.py` cobre a matriz:
  - requested `tts_1_5b`, executed `tts_1_5b`, fallback false: permitido;
  - requested `tts_1_5b`, executed `chatterbox-tts-pt-br`, fallback false: rejeitado;
  - requested `chatterbox-tts-pt-br`, executed `tts_1_5b`, fallback false: rejeitado;
  - requested `tts_1_5b`, executed `tts_1_5b`, fallback true: rejeitado;
  - requested `chatterbox-tts-pt-br`, executed `chatterbox-tts-pt-br`, fallback true: rejeitado;
  - engine solicitada valida com `engine_key` ausente: rejeitado.
- `tests/test_tts_forbidden_runtime_paths.py` usa raiz absoluta calculada pelo arquivo e nao depende do cwd.
- `tests/test_tts_realtime_worker.py` rejeita worker com sucesso sem `engine_key`.
- Busca funcional proibida por `win32com`, `pyttsx3`, `System.Speech`, `SpVoice`,
  `PRESET_VOICES`, `PRESET_IDS`, `math.sin`, `np.sin`, `_write_sine` e
  `_synthetic_smoke_*` em `main.py`, `services`, `workers`, `routers`,
  `static` e `scripts`: sem ocorrencias.
- Busca ampla classificada:
  - funcional proibido: nenhuma ocorrencia;
  - documentacao: docs do escopo, baseline, relatorio e proposta de tracker;
  - compatibilidade rejeitora: mensagens de erro e parametros que recusam fallback proibido;
  - migracao/rejeicao de legado: `services/config_store.py`, `services/voice_profiles.py`, `static/js/voice_library.js`;
  - metadados permitidos: campos `fallback=false` e status visual;
  - testes negativos: arquivos `tests/test_tts_*` e `tests/test_voice_profiles.py`;
  - falsos positivos: fallback de hardware/NVML/transcricao fora do TTS proibido.

## Itens nao executados

Nenhum teste obrigatorio ficou pendente.

## Pendencias Gate B

- T2.1: versionar `profile.json`.
- T2.2: migracao idempotente do modelo de dados de voz.
- T2.3: preservar vozes reais antigas e separar derivados por engine.
- Nao iniciar parser, RenderPlan, UI de estilos ou Realtime nativo antes dos gates correspondentes.

## Diff final

Diff revisado apos testes. Arquivos principais:

- codigo: `main.py`, `services/config_store.py`, `services/voice_profiles.py`,
  `services/vibevoice_tts_1_5b.py`, `services/chatterbox_adapter.py`,
  `services/vibevoice_realtime_0_5b.py`, `static/js/voice_library.js`;
- testes: `tests/test_tts_legacy_voice_migration.py`,
  `tests/test_tts_no_fallbacks.py`,
  `tests/test_tts_forbidden_runtime_paths.py`,
  `tests/test_tts_realtime_worker.py`,
  `tests/test_tts_orchestration.py`;
- auditoria: `CONTEXT.md`, `docs/tts/EXECUTION_STATUS.md`,
  `docs/tts/gate-a-report.md`, `docs/tts/TRACKER_UPDATE_PROPOSAL.md`,
  `docs/tts/gate-a-review-package.md`.
