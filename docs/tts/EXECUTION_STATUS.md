# TTS Execution Status

Data: 2026-07-15

Fonte de verdade do progresso auditável. Estado curto e próxima ação ficam em
`docs/tts/CURRENT_RUNWAY.md`; contratos ficam na especificação e nas issues.

Estados válidos:

- `not_started`;
- `in_progress`;
- `implemented` — código/artefato existe, mas aceite ainda não foi integralmente provado;
- `verified` — todos os critérios possuem evidência explícita;
- `blocked`;
- `superseded`.

## Regra de verificação

Uma linha só recebe `verified` quando cada critério de aceite está mapeado para
teste, diff, documento ou evidência. Suíte verde isolada não comprova critérios
não exercitados. Auditoria posterior pode rebaixar o estado e reabrir a issue.

## Gate A — confiança e remoção de fallbacks

| ID | Tarefa | Estado | Evidência principal | Observação |
| --- | --- | --- | --- | --- |
| T0.1 | Baseline auditável | verified | `docs/tts/gate-a-baseline.md` | Referência histórica preservada. |
| T0.2 | Escopo e precedência | verified | `CONTEXT.md`, escopo em `docs/tts/` | Fontes canônicas roteadas. |
| T1.1 | Remover presets Windows | verified | testes de migração/vozes | Sem presets como produção. |
| T1.2 | Remover SAPI5/senoide/smoke | verified | testes de caminhos proibidos | Falha explícita preservada. |
| T1.3 | Testes negativos | verified | testes de no-fallback | Barreira de regressão. |
| T9.3 | Large sem referência artificial | verified | testes de erro claro | Validação real futura. |
| T10.1 | Realtime sem smoke sintético | verified | testes do worker | Realtime nativo segue separado. |

## Gate B — voz real, estilos, eventos e primeira voz

| ID | Issue | Tarefa | Estado | Evidência resumida |
| --- | --- | --- | --- | --- |
| T2.1 | — | Schema de voz v2 | verified | migração idempotente e derivados por engine; suíte registrada no histórico. |
| T2.2 | #16 | Entidade Style | verified | CRUD, aliases, parâmetros, compatibilidade, referência opcional e rollback. |
| T2.3 | #17 | Entidade Event | verified | eventos canônicos, mídia, metadados, erros e rollback. |
| T3.1 | #18 | Captura real no wizard | verified | gravação/upload, consentimento, escuta e voz padrão. |
| T3.2 | #19 | Texto de captura | verified | orientação e permanência no fluxo de gravação. |
| T3.3 | #20 | Referência por engine | verified | original preservado, referência Chatterbox e diagnóstico de qualidade. |

## Gate C — linguagem, validação e RenderPlan

Epic operacional: #26
Contrato específico: `docs/tts/RENDERPLAN_CONTRACT.md`

| ID | Issue | Tarefa | Estado | Entregue | Lacuna / próximo passo | Dependência |
| --- | --- | --- | --- | --- | --- | --- |
| T4.1 | #21 | Gramática formal | verified | EBNF, exemplos e fronteiras. | Nenhuma nesta tarefa. | T3.3 |
| T4.2 | #22 | Parser e AST | verified | nós de estilo, pausa, evento, subtítulo e erros com posição. | Nenhuma nesta tarefa. | T4.1 |
| T4.3 | #23 | Validação contra biblioteca | verified | validação pura de estilo, alias, speaker, evento e compatibilidade. | Sem RenderPlan por contrato. | T4.2 |
| T5.1 | #24 | RenderPlan persist?vel | verified | jobs ordenados e serializ?veis preservam se??o, ordem, voz, estilo, refer?ncia relativa, par?metros e textos original/normalizado; identidade determin?stica cobre toda a sem?ntica de T5.1. | `31bd3ca0`; `19 passed` focais; `265 passed, 4 warnings` na su?te completa; `git diff --check` limpo. #24 pronta para fechamento e #25 pode ser retriada. | T4.3 |
| T5.2 | #25 | Falantes reais e virtuais | verified | cada job registra speaker logico, voz, estilo canonico, referencia relativa e parametros tipados; aliases resolvem por voz; estilos prontos usam midia propria; falhas sao explicitas. | `a8ffa8d7`; `24 passed` focais; `270 passed, 4 warnings` na suite completa; `git diff --check` limpo. | T5.1 |
| T6.1 | #30 | Normalizador PT-BR modular | verified | regras textuais removidas de `tts_orchestration.py` e centralizadas em `services/pt_br_normalizer.py`, com perfis explicitos por engine e falha para perfil desconhecido. | `d02fc83e`; `30 passed` focais; `276 passed, 4 warnings` na suite completa; `git diff --check` limpo. | T5.2 |
| T6.2 | #31 | Cobertura PT-BR ampliada | verified | datas completas, horas, moeda, percentuais, unidades, abreviacoes, siglas e dicionario por chamada; URLs, e-mails e telefones protegidos; numeros ate 999.999.999 e acentuacao canonica. | `37 passed` focais; `283 passed, 4 warnings` na suite completa; `git diff --check` limpo. | T6.1 |
| T7.1 | #32 | AudioAssembler determinístico | verified | WAV PCM mono a 24 kHz; ordem, pausas e eventos na timeline; normalização de canais/sample rate; fades de borda; manifesto final serializável. | `29 passed` focais; `287 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T6.2 |
| T7.2 | #33 | Regeneração individual por cache | verified | cache persistente por `job_id`, atualização isolada e remontagem usando segmentos existentes; identidade e timeline T7.1 preservadas. | `31 passed` focais; `289 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T7.1 |
| T7.3 | #34 | Transição de estilo por crossfade | verified | crossfade linear de 20 ms apenas em mudança adjacente de `style_id`; pausas/eventos interrompem a transição; manifesto registra duração e transição. | `34 passed` focais; `292 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T7.2 |
| T8.1 | #35 | Parâmetros reais do Chatterbox | verified | registry `tts_chatterbox`, defaults/clamp, filtragem por assinatura, overrides por segmento e metadados dos valores usados. | `20 passed` focais; `294 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T7.3 |
| T8.2 | #36 | Referência Chatterbox por segmento | verified | referências individuais encaminhadas por chunk, erro explícito para ausência e `references_by_segment` no metadata; compatibilidade neutra preservada. | `21 passed` focais; `295 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T8.1 |
| T8.3 | #37 | Multi-voz Chatterbox orquestrado | verified | cada segmento resolve speaker/voz/referência de forma independente, gera chamadas separadas, rejeita mapa ausente e retorna `speakers_by_segment`, `voices_by_segment` e `references_by_segment`. | `35 passed` focais; `296 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T8.2 |
| T8.4 | #38 | Cancelamento e unload Chatterbox | verified | token cooperativo verificado antes do primeiro e de cada segmento; cancelamento impede chamadas seguintes; wrapper propaga token e descarrega modelo/VRAM no pós-job solicitado. | `16 passed` focais; `298 passed, 4 warnings` na suíte completa; `git diff --check` limpo. | T8.3 |

## Bloqueios independentes

| Issue | Tipo | Estado | Impacto |
| --- | --- | --- | --- |
| #8 | HITL — Realtime 0.5B | blocked | Bloqueia somente a frente nativa do Realtime, não Gate C. |
| #12 | Validação final | blocked | Depende de gates posteriores e de evidência real em hardware. |


## Reconcilia??o de T5.1

T5.1 foi conclu?da no commit `31bd3ca0`. O manifesto agora preserva `section_id` e `section_title`, mant?m ordem entre e dentro das se??es, rejeita refer?ncias absolutas e deriva `job_id` de se??o, ordem, voz, estilo, refer?ncia, par?metros e textos original/normalizado.

Evid?ncia: `19 passed` em `tests/test_tts_orchestration.py`; `265 passed, 4 warnings` na su?te completa; `git diff --check` sem erros.

## Pr?ximo passo permitido

1. fechar #24 com mapa aceite ? evid?ncia;
2. retriar #25 como `ready-for-agent`;
3. executar exclusivamente #25/T5.2 conforme `RENDERPLAN_CONTRACT.md`;
4. n?o alterar engines, endpoints, UI, AudioAssembler ou Realtime.

## Proximo passo permitido

1. fechar #30 com mapa aceite -> evidencia;
2. formalizar T6.2 como proxima fatia executavel;
3. ampliar cobertura linguistica somente em T6.2, mantendo API modular;
4. preservar T6.3 para preview e regras por engine.

## Proximo passo permitido

1. fechar #32 com mapa aceite -> evidência;
2. formalizar T7.2 como unidade executável de cache e remontagem;
3. não iniciar T6.3, engines, UI ou T7.3 na issue seguinte.

## Decisão consolidada de T7.3

Crossfade linear fixo de 20 ms somente entre segmentos consecutivos com mudança de `style_id`; pausas e eventos interrompem a adjacência, sem alteração de pitch.

## Próximo passo permitido

1. fechar #34 com mapa aceite -> evidência;
2. formalizar T8.1 como próxima fatia executável;
3. preservar T8.2 e engines posteriores para as issues seguintes.

## Próximo passo permitido

1. fechar #34 com mapa aceite -> evidência;
2. formalizar T8.1 como fatia executável de parâmetros Chatterbox;
3. preservar T8.2 (referência por segmento) para a issue seguinte.
