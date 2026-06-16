# Gate A - Relatorio de execucao

Data: 2026-06-16

Branch: `codex/tts-gate-a`

Commit-base: `b342721c34d883bf9769a3f6c066188b4e29f2a4`

Fonte de verdade: `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`

## Escopo executado

Gate A restaurou confianca no subsistema TTS removendo caminhos funcionais proibidos de audio falso.

Tarefas cobertas:

- T0.1: baseline auditavel registrado em `docs/tts/gate-a-baseline.md`.
- T0.2: escopo TTS registrado em `docs/tts/` e apontado por `CONTEXT.md`.
- T1.1: presets Windows deixaram de existir como vozes resolviveis.
- T1.2: SAPI5 e senoide foram removidos de runtime/adapters/scripts de diagnostico.
- T1.3: testes negativos globais foram adicionados contra regressao.
- T9.3: VibeVoice Large permanece bloqueado sem referencias reais por speaker.
- T10.1: worker Realtime nao retorna synthetic smoke e o cliente recusa audio sintetico.

## Decisoes preservadas

- Uma solicitacao usa uma engine ou falha explicitamente.
- Nenhum fallback de engine, voz ou audio e aceito.
- Presets Windows, SAPI5, senoide e smoke sintetico nao sao caminhos validos de producao.
- Large so pode executar com referencias reais.
- Realtime 0.5B so pode ficar disponivel depois de PCM/WAV nativo real validado.
- O prompt/PRD antigo e historico e nao limita o escopo atual.

## Validacao

Comando final executado:

```powershell
python -m pytest
```

Resultado final:

- `204 passed`
- `2 warnings`

Warnings conhecidos:

- Deprecation warnings de `FastAPI.on_event`, ja existentes e fora do escopo do Gate A.

Busca direcionada de caminhos proibidos:

```powershell
rg -n "_build_voice_samples|_create_voice_prompt_wav|_write_sine_voice_prompt|_synthetic_smoke_(enabled|response|pcm_bytes)|synthetic_smoke_enabled|win32com|SpVoice|math\.sin|np\.sin" services workers scripts main.py static
```

Resultado: sem ocorrencias funcionais.

## Protecoes adicionadas

- `tests/test_tts_forbidden_runtime_paths.py` falha se imports/geradores proibidos voltarem ao codigo de producao.
- `tests/test_tts_no_fallbacks.py` falha se `/api/tts/generate` devolver audio de engine diferente da solicitada ou com fallback.
- `tests/test_tts_realtime_worker.py` falha se Realtime aceitar/retornar synthetic smoke.
- `tests/test_tts_large_clear_errors.py` falha se Large tentar carregar antes de referencias reais.

## Proximo gate planejado

Gate B deve comecar por T2.1:

1. versionar `profile.json`;
2. garantir migracao idempotente;
3. preservar vozes reais antigas;
4. separar derivados por engine;
5. preparar o caminho para estilos e eventos persistidos.

Nao iniciar parser, RenderPlan ou UI de estilos antes de estabilizar o modelo de dados do Gate B.
