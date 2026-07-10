# Continuidade e retomada de sessão limpa

## Quando carregar

Carregue este arquivo quando a tarefa envolver retomada, sessão com contexto
limpo, pedido de “continue”, fim de rodada, risco de perda de contexto, handoff,
commit, ledger, issue ativa ou estado recuperável.

## Contrato de continuidade

Toda rodada não trivial deve persistir estado suficiente para retomada em sessão
limpa. O estado persistido deve responder:

* qual tarefa/issue está ativa;
* objetivo;
* escopo;
* fora de escopo;
* arquivos relevantes ou alterados;
* decisões já tomadas;
* testes e verificações executados;
* pendências;
* fila de trabalho executável;
* próxima ação recomendada;
* critério de parada;
* riscos;
* recomendação de orquestração.

O handoff conversacional não substitui estado persistido. Se o estado estiver no
GitHub, `$handoff` não é obrigatório. Se algo necessário existir apenas no chat,
persista em issue, ledger, plano ou documento de status; se isso não for
possível, gere `$handoff` textual explícito.

## Bootstrap de sessão limpa

Ao receber “Execute o AGENTS.md e continue”, o agente deve:

1. ler `AGENTS.md`;
2. carregar este documento;
3. carregar `docs/agents/AUTONOMOUS_RUNWAY.md` quando houver fila, backlog,
   múltiplas frentes, bloqueios ou continuidade autônoma;
4. carregar `docs/agents/MODEL_ROUTING.md` para recomendação de modelo, esforço e
   subagentes;
5. carregar `docs/agents/SKILL_ROUTING.md` se a tarefa não for trivial;
6. carregar `docs/agents/AUTONOMY_AND_GIT.md` se houver issue, edição, commit,
   push ou ação remota;
7. ler `CONTEXT.md` quando a tarefa envolver domínio, produto ou TTS;
8. inspecionar `git status --short --branch` quando houver ambiente local
   disponível;
9. identificar a tarefa ativa e a fila de tarefas aplicável por issues, planos,
   ledgers, documentos de status e arquivos modificados;
10. ler somente os documentos de continuidade diretamente aplicáveis;
11. reconstruir objetivo, escopo, fora de escopo, critérios de aceite, testes
    mínimos, fila executável, próxima ação e critério de parada.

Não carregue o repositório inteiro por padrão. Comece por índice, mapas, buscas
dirigidas e leitura sob demanda.

## Execução contínua até bloqueio real

Uma sessão limpa deve reconstruir não apenas a próxima tarefa isolada, mas a fila
de tarefas executáveis. O orquestrador deve distinguir:

* tarefas prontas;
* tarefas bloqueadas por dependência técnica;
* tarefas bloqueadas por decisão humana;
* tarefas fora de escopo;
* tarefas paralelizáveis;
* tarefas sequenciais.

Se uma tarefa ficar bloqueada por decisão humana, registre o bloqueio e verifique
se há outra tarefa independente, delimitada e autorizada que possa avançar sem
esperar o usuário. O agente só deve parar para HITL quando:

* a decisão humana bloqueia todas as próximas ações úteis; ou
* continuar criaria risco de escopo, produto, segurança ou perda de trabalho; ou
* faltam critérios de aceite para qualquer próxima ação segura.

Quando houver trabalho paralelo seguro, continue na próxima frente desbloqueada.
Ao fim da rodada, registre no GitHub quais frentes foram concluídas, quais
ficaram bloqueadas e por quê.

## Quando o comando mínimo é suficiente

“Execute o AGENTS.md e continue” é suficiente quando:

* existe uma tarefa ativa ou fila executável identificável;
* há issue, plano, ledger ou documento de status com próxima ação clara;
* o estado Git não contém alterações inexplicadas;
* critérios de aceite e parada estão claros;
* não há decisão humana bloqueando todas as próximas ações úteis;
* a próxima ação está dentro da autorização permanente do repositório.

Não é suficiente quando:

* há múltiplas tarefas ativas indistinguíveis;
* arquivos locais modificados não estão explicados;
* falta critério de aceite;
* há decisão humana bloqueando todas as próximas ações úteis;
* a próxima ação depende de contexto que só existe no chat anterior;
* há risco de sobrescrever trabalho não compreendido.

## GitHub como memória primária

O estado recuperável mínimo é:

* commits publicados;
* issue atualizada quando aplicável;
* ledger/status atualizado quando aplicável;
* plano ou documento de continuidade atualizado;
* testes/verificações registrados;
* fila concluída, fila bloqueada e próxima execução recomendada.

Uma sessão limpa deve conseguir continuar lendo `AGENTS.md`, este arquivo,
`docs/agents/AUTONOMOUS_RUNWAY.md`, `CONTEXT.md`, documentos de continuidade e a
issue ativa. Se uma rodada termina com working tree sujo, isso é exceção e deve
ser explicado com arquivos afetados, risco e próximo passo seguro.

## Invariante de continuidade

Ao final de qualquer rodada não trivial, deve ser possível abrir uma sessão limpa
e continuar com “Execute o AGENTS.md e continue”. Se isso não for verdade,
atualize os arquivos de continuidade aplicáveis ou gere `$handoff`.

## Estado atual conhecido do TTS

No estado registrado em 2026-07-10:

* `#16` está concluída;
* `#17` está concluída;
* `#18` é a próxima execução formal (`T3.1 — captura real da primeira voz no
  wizard`) e está classificada como `Ready`;
* `#8` está classificada como `Blocked-human` para Realtime nativo;
* `#12` está bloqueada por lacunas posteriores e não é a próxima execução
  operacional;
* `T4.x` está fora de escopo até concluir `#18` e formalizar a ordem posterior;
* a continuidade principal está em `docs/tts/EXECUTION_STATUS.md`,
  `docs/tts/ISSUE_EXECUTION_PLAN.md` e issue `#18`.

O orquestrador pode iniciar e concluir `#18` autonomamente se a issue continuar
delimitada e os testes forem proporcionais. Quando esse estado mudar, atualize o
ledger/status e a issue correspondente, não apenas este resumo.
