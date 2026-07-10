# Continuidade e retomada de sessão limpa

## Quando carregar

Carregue este arquivo quando a tarefa envolver retomada, sessão com contexto
limpo, pedido de “continue”, fim de rodada, risco de perda de contexto, handoff,
commit, ledger, issue ativa ou estado recuperável.

## Contrato de continuidade

Toda rodada não trivial deve persistir estado suficiente para retomada em sessão
limpa. O estado persistido deve responder:

- qual tarefa/issue está ativa;
- objetivo;
- escopo e fora de escopo;
- arquivos relevantes ou alterados;
- decisões já tomadas;
- testes e verificações executados;
- pendências e riscos;
- fila executável;
- próxima ação;
- critério de parada;
- recomendação de orquestração.

Handoff conversacional não substitui estado persistido. Se o estado estiver no
GitHub, `$handoff` não é obrigatório. Se algo necessário existir apenas no chat,
persista em issue, ledger, plano ou runway; se isso não for possível, gere
`$handoff` explícito.

## Bootstrap de sessão limpa

Ao receber “Execute o AGENTS.md e continue”:

1. ler `AGENTS.md`;
2. carregar este documento;
3. carregar `docs/agents/AUTONOMOUS_RUNWAY.md` quando houver fila ou bloqueios;
4. carregar `docs/agents/MODEL_ROUTING.md` para modelo/esforço/subagentes;
5. carregar `docs/agents/SKILL_ROUTING.md` se a tarefa não for trivial;
6. carregar `docs/agents/AUTONOMY_AND_GIT.md` se houver alteração ou ação remota;
7. ler `CONTEXT.md` para tarefas de domínio/produto;
8. inspecionar `git status --short --branch` quando houver ambiente local;
9. identificar tarefa ativa e fila por issues, planos, ledgers e arquivos modificados;
10. ler somente os documentos diretamente aplicáveis;
11. reconstruir objetivo, escopo, aceite, testes, próxima ação e parada.

Não carregue o repo inteiro. Comece por índices, cursor curto, issue ativa e busca
dirigida.

## Execução contínua até bloqueio real

Uma sessão limpa deve reconstruir a fila, distinguindo:

- `Ready`;
- `Blocked-human`;
- `Blocked-technical`;
- `Out-of-scope`;
- `Parallelizable`;
- `Sequential`;
- `Done`.

Se uma tarefa ficar bloqueada por decisão humana, registre e procure outra frente
independente. Pare para HITL somente quando a decisão bloquear todas as próximas
ações úteis, continuar criar risco material ou faltar aceite para qualquer ação
segura.

## Quando o comando mínimo é suficiente

“Execute o AGENTS.md e continue” é suficiente quando:

- há tarefa ativa ou fila identificável;
- existe issue/plano/ledger/runway com próxima ação clara;
- o Git não contém alterações inexplicadas;
- aceite e parada estão claros;
- não há decisão humana bloqueando tudo;
- a ação está dentro da autorização permanente.

Não é suficiente quando há múltiplas tarefas indistinguíveis, contexto apenas no
chat, working tree inexplicado ou risco de sobrescrever trabalho não compreendido.

## GitHub como memória primária

O estado recuperável mínimo é:

- commits publicados;
- issue atualizada;
- ledger/status atualizado quando aplicável;
- runway ou plano atualizado quando a fila mudar;
- testes/verificações registrados;
- próxima execução e bloqueios claros.

Ao final de rodada não trivial, deve ser possível continuar em sessão limpa. Se
não for, atualize a memória do repo ou gere `$handoff`.

## Estado de domínios específicos

Este arquivo não mantém estado mutável de TTS nem de outros subsistemas.

Para TTS, leia nesta ordem:

1. `docs/tts/CURRENT_RUNWAY.md`;
2. issue ativa;
3. `docs/tts/README.md` para roteamento;
4. `docs/tts/EXECUTION_STATUS.md` quando precisar de evidência/histórico;
5. `docs/tts/ISSUE_EXECUTION_PLAN.md` quando houver DAG ou múltiplas frentes.

Se algum documento genérico voltar a duplicar estado datado do TTS, remova a
duplicação e preserve o estado apenas nas fontes acima.