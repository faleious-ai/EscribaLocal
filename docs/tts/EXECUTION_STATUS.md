# TTS Execution Status

Data: 2026-06-16

Fonte de verdade de progresso para o subsistema TTS. Estados validos:
`not_started`, `in_progress`, `implemented`, `verified`, `blocked`,
`superseded`.

## Gate A

| ID | Nome | Gate | Estado | Branch | PR | Commit | Evidencia | Testes | Pendencias | Dependencias | Proximo passo permitido |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T0.1 | Congelar baseline auditavel | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` sobre base `b342721c` | `docs/tts/gate-a-baseline.md` registra commit-base, suite inicial e busca estatica inicial. | Baseline anterior: `python -m pytest` com `200 passed`. | Nenhuma. | Nenhuma. | Manter baseline como referencia historica; nao editar para reduzir criterio. |
| T0.2 | Registrar escopo e precedencia | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | `CONTEXT.md` aponta escopo, ledger e relatorio do gate; escopo versionado em `docs/tts/`. | `python -m pytest` -> `217 passed`, `2 warnings`; `git diff --check` sem erro. | Nenhuma nesta rodada. | T0.1. | Revisao externa do Gate A; depois Gate B pode iniciar por T2.1. |
| T1.1 | Remover presets Windows como vozes validas | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | `services/voice_profiles.py` nao expoe `is_preset`; adapters rejeitam IDs legados; `services/config_store.py` migra config/perfis; `static/js/voice_library.js` migra localStorage. | `tests/test_tts_legacy_voice_migration.py` -> `5 passed`; `tests/test_voice_profiles.py` -> `23 passed`; suite completa -> `217 passed`. | Nenhuma nesta rodada. | T0.2. | Revisar Gate A; nao iniciar criacao de primeira voz do Gate B ainda. |
| T1.2 | Remover SAPI5/senoide/smoke funcional | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | Runtime 1.5B/Large/Realtime nao contem geradores SAPI5, senoide ou smoke sintetico; mensagens de erro rejeitam esses caminhos. | `tests/test_tts_forbidden_runtime_paths.py` -> `1 passed`; fora da raiz -> `1 passed`; busca funcional proibida sem ocorrencias. | Nenhuma nesta rodada. | T1.1. | Revisao externa do Gate A. |
| T1.3 | Testes negativos contra regressao | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | Teste global usa raiz do arquivo; matriz de engine exige `engine_key` explicita e `fallback=false`. | `tests/test_tts_no_fallbacks.py` -> `13 passed`; `tests/test_tts_realtime_worker.py` -> `21 passed`; suite completa -> `217 passed`. | Nenhuma nesta rodada. | T1.1, T1.2. | Revisao externa; manter testes como barreira antes do Gate B. |
| T9.3 | Corrigir Large para vozes reais | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | Large permanece indisponivel sem referencias reais por speaker; amostra artificial nao e caminho valido. | `tests/test_tts_large_clear_errors.py` -> `5 passed`; busca por `_build_voice_samples` sem ocorrencias. | Nenhuma nesta rodada. | T1.2. | Gate B nao altera Large; futura retomada fica em Gate D/F conforme escopo. |
| T10.1 | Remover synthetic smoke do runtime Realtime | A | verified | `codex/tts-gate-a` | #15 draft | `b75ed41b` + diff local desta rodada | Cliente do worker rejeita sucesso sem `engine_key`; worker nao anuncia synthetic smoke como capacidade. | `tests/test_tts_realtime_worker.py` -> `21 passed`; suite completa -> `217 passed`; busca funcional proibida sem ocorrencias. | Nenhuma nesta rodada. | ADR `0001`. | Realtime nativo so pode avancar em T10.2, fora do Gate A. |

## Gates Posteriores

Gate B permanece `not_started` nesta branch. O proximo passo permitido depois
da revisao do Gate A e T2.1: versionar `profile.json` e preparar migracao
idempotente do modelo de dados, sem parser, RenderPlan ou UI de estilos ainda.
