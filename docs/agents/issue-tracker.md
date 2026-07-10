# Issue Tracker

Issues e PRDs deste repositório vivem no GitHub Issues de
`faleious-ai/EscribaLocal`.

## Papel das issues

Uma issue operacional é um contrato executável, não apenas uma anotação de
backlog. Ela deve permitir que uma sessão limpa execute o trabalho sem
reinterpretar intenção.

## Estrutura mínima de issue AFK

- Parent/epic;
- Gate e Task ID;
- objetivo;
- escopo;
- fora de escopo;
- critérios de aceite verificáveis;
- dependências;
- plano de evidência;
- testes mínimos;
- riscos;
- critério de parada.

## Estrutura mínima de issue HITL

- decisão necessária;
- por que não pode ser resolvida no repo;
- opções concretas;
- evidências disponíveis;
- recomendação;
- consequência de cada opção;
- tarefas independentes que continuam executáveis.

## Hierarquia e dependências

Quando o ambiente disponibilizar recursos nativos:

- use sub-issues para decomposição hierárquica;
- use dependências nativas para relações `blocked by`/`blocking`;
- use milestone para agrupar um gate;
- use GitHub Project para visualização da fila.

Esses recursos não substituem a especificação, o ledger ou o runway. Se o
conector não expuser as operações nativas, registre temporariamente a hierarquia
e o DAG na epic e nas issues, sem fingir que a dependência nativa foi criada.

## Labels

Use os rótulos canônicos definidos em `docs/agents/triage-labels.md`. Labels
indicam prontidão/triagem; estado operacional detalhado pertence ao runway ou ao
campo Status do Project quando disponível.

## Checkpoint

Comentários de checkpoint devem registrar:

- commit ou estado da alteração;
- critérios já atendidos;
- testes executados;
- pendências;
- próximo passo;
- impacto sobre dependentes.

## Fechamento

Antes de fechar, siga `docs/agents/AUTONOMY_AND_GIT.md`. O comentário final deve
mapear cada critério de aceite à evidência correspondente. Suíte verde sem prova
do critério não é suficiente.

## Reabertura

Reabra quando auditoria demonstrar aceite explícito incompleto. Registre a lacuna,
preserve a evidência da entrega parcial, corrija ledger/runway e bloqueie
dependentes até novo fechamento.

## Convenções de CLI

- criar: `gh issue create`;
- ler com comentários: `gh issue view <numero> --comments`;
- listar: `gh issue list`;
- comentar: `gh issue comment <numero>`;
- labels: `gh issue edit <numero> --add-label "..."`;
- fechar: `gh issue close <numero>`;
- reabrir: `gh issue reopen <numero>`.

Quando uma skill pedir publicação, use o tracker real. Não mantenha drafts
paralelos depois que a issue existir.