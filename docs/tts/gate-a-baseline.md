# Gate A - Baseline auditavel

Data: 2026-06-16

## T0.1 - Congelar baseline auditavel

### Commit-base

- Branch original: `main`
- Branch de trabalho: `codex/tts-gate-a`
- Commit-base: `b342721c34d883bf9769a3f6c066188b4e29f2a4`

### Testes atuais

Comando executado:

```powershell
python -m pytest
```

Resultado:

- `200 passed`
- `2 warnings`
- Tempo: `44.23s`

Observacao de ambiente:

- A primeira execucao falhou porque `imageio-ffmpeg` nao estava instalado no ambiente local.
- A dependencia ja estava pinada em `requirements.txt` como `imageio-ffmpeg==0.6.0`.
- A versao pinada foi instalada e a suite completa passou em seguida.

### Busca estatica inicial de caminhos proibidos

Comando executado:

```powershell
rg -n "SAPI|win32com|System\.Speech|pyttsx3|sine|synthetic_smoke|PRESET_VOICES|preset_windows|voz Windows|Windows" services workers routers static scripts main.py tests
```

Referencias funcionais ou legitimadoras encontradas antes das correcoes:

- `services/voice_profiles.py`: define `PRESET_VOICES`, `PRESET_IDS`, aliases legados e resolucao de presets Windows.
- `services/vibevoice_tts_1_5b.py`: contem geracao de referencia via SAPI5, fallback para senoide e caminho Large baseado em amostra artificial.
- `workers/vibevoice_realtime_worker.py`: expoe `synthetic_smoke`, gera PCM sintetico e pode retornar audio de smoke quando habilitado.
- `scripts/diag_tts_roundtrip.py`: ainda usa SAPI5 como referencia limpa para diagnostico.
- `tests/test_tts_realtime_worker.py`: ainda espera audio `synthetic_smoke` em alguns contratos.
- `tests/test_tts_no_fallbacks.py`, `tests/test_tts_real_voices_required.py` e `tests/test_voice_profiles.py`: contem cobertura parcial contra fallback, mas ainda convivem com nomes e caminhos legados.

Referencias descritivas permitidas por enquanto:

- Mensagens que rejeitam SAPI5, tom sintetico, presets Windows ou fallback automatico.
- Texto de documentacao que descreve a remocao planejada.
- Comentarios ou textos sobre Windows enquanto sistema operacional, sem relacao com voz Windows.

### Protecao de trabalho do usuario

- `git status --short` inicial indicava dois arquivos nao versionados: `ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md` e `PROMPT_MESTRE_TTS_ESCRIBALOCAL.md`.
- Esses arquivos foram preservados.
- Nenhuma alteracao existente do usuario foi descartada.
