# Contexto do EscribaLocal

Este repositorio e de contexto unico. Antes de planejar ou alterar comportamento nao trivial, leia os documentos de dominio e ADRs relevantes.

## Fonte de verdade atual para TTS

O subsistema TTS deve seguir, nesta ordem:

1. decisoes explicitas mais recentes do usuario;
2. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`;
3. `docs/tts/EXECUTION_STATUS.md`;
4. `docs/tts/gate-a-report.md` ou o relatorio do gate atual;
5. ADRs aceitos que nao contradigam esse escopo;
6. instrucoes operacionais em `AGENTS.md` e `docs/agents/`.

Leia esses tres documentos de TTS em conjunto antes de planejar ou alterar o
subsistema: o escopo define decisoes e sequencia, o ledger registra o estado
auditavel das tarefas, e o relatorio do gate mostra o que foi validado,
bloqueado ou movido para o proximo gate.

## Documentos historicos de TTS

`PROMPT_MESTRE_TTS_ESCRIBALOCAL.md` e a PRD historica sobre "TTS local verificavel com VibeVoice e Chatterbox PT-BR" devem ser tratados como registro historico. Eles nao limitam o escopo atual quando divergirem de `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`.

Conflitos ja resolvidos pelo escopo atual:

- estilos personalizados pertencem a voz e nao sao apenas presets globais;
- tags usam diretamente o nome do estilo, nao a sintaxe provisoria `[style:...]`;
- subtitulos Markdown sao metadados nao falados;
- falantes virtuais e multiplas vozes usam orquestracao por segmentos;
- SAPI5, vozes Windows, senoide e smoke sintetico nao sao caminhos de producao validos;
- a PRD antiga nao inclui todo o escopo de estilos, eventos, subtitulos, montagem por timeline e RenderPlan.

## ADRs relevantes

- `docs/adr/0001-isolar-vibevoice-realtime-por-subprocesso.md`
