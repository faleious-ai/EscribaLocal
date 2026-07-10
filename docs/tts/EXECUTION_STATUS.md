# TTS Execution Status

Data: 2026-07-10

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
| T5.1 | #24 | RenderPlan persistível | implemented | jobs ordenados, serialização, voz, estilo, referência, parâmetros e textos. | **Issue reaberta:** seções não são preservadas; ID não cobre toda a semântica; falta mapa aceite→evidência. Concluir sem avançar T5.2. | T4.3 |
| T5.2 | #25 | Falantes reais e virtuais | blocked | issue existente e contrato aprofundado. | Aguardar #24; depois resolver por segmento `speaker → voice → style → reference → parameters`. | T5.1 |

## Bloqueios independentes

| Issue | Tipo | Estado | Impacto |
| --- | --- | --- | --- |
| #8 | HITL — Realtime 0.5B | blocked | Bloqueia somente a frente nativa do Realtime, não Gate C. |
| #12 | Validação final | blocked | Depende de gates posteriores e de evidência real em hardware. |

## Reconciliação de T5.1

A issue #24 foi fechada com registro de `260 passed`, mas o critério explícito de
preservação de seções não possui implementação/evidência no manifesto atual. O
estado foi rebaixado de `verified` para `implemented`; o trabalho entregue não é
apagado. A issue está reaberta e delimitada para concluir o aceite antes de #25.

## Próximo passo permitido

1. concluir exclusivamente #24/T5.1 conforme `RENDERPLAN_CONTRACT.md`;
2. registrar aceite → evidência;
3. fechar #24 somente após testes;
4. retriar #25 como `ready-for-agent`;
5. atualizar este ledger e `CURRENT_RUNWAY.md`.

Não iniciar código de #25, engines, UI, AudioAssembler, montagem ou Realtime antes
dessa sequência.