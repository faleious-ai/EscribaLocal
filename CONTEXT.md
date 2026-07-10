# Contexto do EscribaLocal

Este repositório é de contexto único. Antes de planejar ou alterar comportamento
não trivial, leia os documentos de domínio e ADRs relevantes.

## Fonte de verdade atual para TTS

O subsistema TTS deve seguir, nesta ordem:

1. decisões explícitas mais recentes do usuário;
2. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`;
3. contratos canônicos específicos, como `docs/tts/RENDERPLAN_CONTRACT.md`;
4. issue ativa delimitada;
5. `docs/tts/CURRENT_RUNWAY.md`;
6. `docs/tts/EXECUTION_STATUS.md`;
7. relatório do gate aplicável;
8. ADRs aceitos que não contradigam esse escopo;
9. instruções operacionais em `AGENTS.md` e `docs/agents/`.

Para retomada, leia primeiro `docs/tts/CURRENT_RUNWAY.md`. Para mapa de carga sob
demanda, leia `docs/tts/README.md`. A especificação define decisões; a issue ativa
define a unidade executável; o ledger registra evidências; o runway é o cursor
curto. Nenhum desses papéis deve ser duplicado em documentos genéricos de agentes.

## Documentos históricos de TTS

`PROMPT_MESTRE_TTS_ESCRIBALOCAL.md`, a PRD histórica sobre “TTS local verificável
com VibeVoice e Chatterbox PT-BR”, drafts de issue e propostas antigas de tracker
são registros de origem. Eles não limitam o escopo atual quando divergirem das
fontes canônicas acima.

Conflitos já resolvidos pelo escopo atual:

- estilos personalizados pertencem à voz e não são apenas presets globais;
- tags usam diretamente o nome/alias do estilo, não a sintaxe provisória `[style:...]`;
- subtítulos Markdown são metadados não falados;
- falantes virtuais e múltiplas vozes usam orquestração por segmentos;
- SAPI5, vozes Windows, senoide e smoke sintético não são produção válida;
- a PRD antiga não inclui todo o escopo de estilos, eventos, subtítulos, montagem por timeline e RenderPlan.

## ADRs relevantes

- `docs/adr/0001-isolar-vibevoice-realtime-por-subprocesso.md`

## Regra de correção de deriva

Se runway, ledger, issue e código divergirem, não escolha silenciosamente o texto
mais conveniente. Audite a evidência, corrija o estado incorreto e registre a
reconciliação no GitHub antes de continuar.