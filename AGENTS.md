# AGENTS.md

Este arquivo é o bootloader operacional obrigatório do repositório. Ele deve
ficar enxuto: carregue sempre este arquivo primeiro e recupere os detalhes sob
demanda pelos documentos indicados abaixo.

Sempre se comunique com o usuário em português do Brasil (pt-BR), inclusive em
perguntas, explicações, relatórios e conclusões. Preserve em inglês apenas
código, comandos, caminhos, identificadores e termos técnicos cuja tradução possa
causar ambiguidade.

## Bootstrap de sessão limpa

Quando recomeçar o trabalho em uma sessão com o contexto limpo:

1. leia este arquivo;
2. carregue `docs/agents/CONTINUATION.md`;
3. carregue `docs/agents/AUTONOMOUS_RUNWAY.md` quando houver fila, backlog,
   múltiplas frentes ou continuidade autônoma;
4. inspecione `git status --short --branch` quando houver ambiente local;
5. identifique a tarefa ativa por issues, planos, ledgers, documentos de status e
   arquivos modificados;
6. leia apenas os documentos de continuidade diretamente aplicáveis;
7. reconstrua objetivo, escopo, fora de escopo, critérios de aceite, testes
   mínimos, próxima ação, fila de trabalho e critério de parada;
8. continue autonomamente quando houver trabalho delimitado, autorizado e
   desbloqueado;
9. peça decisão objetiva ao usuário somente se houver bloqueio humano real que
   impeça todas as próximas ações úteis ou se continuar criaria risco material.

Não carregue o repositório inteiro por padrão. Comece por mapa, busca dirigida e
leitura sob demanda.

## Matriz de carregamento sob demanda

| Situação | Carregar |
| --- | --- |
| Sessão limpa, “continue”, fim de rodada ou risco de perda de contexto | `docs/agents/CONTINUATION.md` |
| Fila, backlog, múltiplas frentes, bloqueios ou execução contínua | `docs/agents/AUTONOMOUS_RUNWAY.md` |
| Issue, commit, push, branch, autonomia ou ação remota | `docs/agents/AUTONOMY_AND_GIT.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md` |
| Tarefa não trivial ou escolha de skill | `docs/agents/SKILL_ROUTING.md` |
| Escolha de modelo, esforço, orquestrador ou subagentes | `docs/agents/MODEL_ROUTING.md` |
| Tarefa de domínio ou produto | `CONTEXT.md`, depois documentos indicados por ele |
| TTS atual | `docs/tts/CURRENT_RUNWAY.md`, depois issue ativa e `docs/tts/README.md` |
| TTS com fila/dependências | `docs/tts/ISSUE_EXECUTION_PLAN.md` |
| TTS com necessidade de evidência/histórico | `docs/tts/EXECUTION_STATUS.md` |
| RenderPlan / Gate C | `docs/tts/RENDERPLAN_CONTRACT.md` |
| Arquitetura ou decisão técnica | ADRs relevantes em `docs/adr/` |
| Ambiente das skills | `docs/agents/skills-runtime.md` |

## Contexto de domínio

Este é um repositório de contexto único. Antes de planejar ou modificar
comportamento não trivial de domínio/produto, leia `CONTEXT.md` e siga a ordem de
precedência definida ali.

Para TTS, o estado atual nunca é inferido de documentos genéricos de agentes.
Leia `docs/tts/CURRENT_RUNWAY.md`; use a especificação para decisões, a issue ativa
como contrato executável e o ledger para evidências. Não trate PRDs, drafts ou
propostas históricas como fila ativa.

Não pergunte ao usuário algo que possa ser descoberto examinando o repositório.

## Execução autônoma contínua

O orquestrador deve executar continuamente todo trabalho delimitado, autorizado e
desbloqueado. Checkpoint, commit, push, comentário em issue, fechamento de issue
ou conclusão de microtarefa não são motivos para parar.

Enquanto houver item `Ready`, o agente não deve devolver o turno. Deve manter o
loop: executar → validar → publicar checkpoint → atualizar memória → reavaliar a
fila → executar o próximo item.

Um bloqueio humano existe somente quando falta decisão, aprovação, acesso ou
validação que não possa ser descoberta nem resolvida com segurança no repo. Ele
não impede frentes independentes prontas.

Quando houver bloqueio humano, use a seção `**BLOQUEIO HUMANO**` e informe:

- o que a pessoa precisa fazer;
- opções concretas;
- recomendação e consequências;
- tarefas que continuam executáveis.

Não peça continuação, confirmação genérica ou autorização já concedida.

## Roteamento obrigatório de skills

Antes de planejar, editar arquivos ou executar mudanças, classifique a tarefa e
use explicitamente a skill instalada mais apropriada. Para tarefa não trivial,
carregue `docs/agents/SKILL_ROUTING.md`.

Informe no início:

`Roteamento: $nome-da-skill — motivo`

Para tarefa realmente trivial:

`Roteamento: execução direta — tarefa trivial e completamente especificada`

Use apenas skills realmente instaladas.

## Modelos, esforço e subagentes

A política normativa está em `docs/agents/MODEL_ROUTING.md`. Use os nomes exatos
da interface e o menor orquestrador, esforço e subagentes suficientes para
entregar com segurança, evidência e qualidade. Não use a capacidade máxima como
padrão.

## GitHub como memória recuperável

GitHub é a fonte primária de continuidade. Ao final de rodada não trivial, o
estado recuperável deve estar em commits, issues, ledger, plano ou runway.

Se houve progresso útil, faça commit e push em `main`, respeitando
`docs/agents/AUTONOMY_AND_GIT.md`. Atualize issue, ledger e runway quando o estado
da fila mudar. Não deixe memória necessária apenas no chat.

`$handoff` é exceção: use somente quando algo essencial ainda não puder ser
persistido no repo.

## Proteções críticas

- inspecione `git status` antes de editar quando houver ambiente local;
- não descarte nem sobrescreva alterações existentes do usuário;
- não amplie escopo sem autorização;
- prefira mudança incremental a reescrita ampla;
- não exponha nem modifique segredos ou credenciais;
- execute testes/verificações proporcionais ao risco;
- revise o diff final;
- uma issue só fecha quando cada critério de aceite possui evidência explícita;
- se auditoria posterior provar aceite incompleto, reabra a issue e corrija o ledger.

## Recomendação final obrigatória

Ao concluir uma etapa ou recomendar continuidade, use:

`Próxima execução: orquestrador <Modelo>, esforço <Leve|Médio|Alto|Extra alto|Ultra>; fila <ready|blocked|empty>: <resumo>; subagentes <nenhum|lista modelo/esforço/função>; decisão humana <não|sim — motivo>; suficiência: <motivo curto>; limite: <restrição de contexto/tokens/escopo>; continuidade: <persistida|requer handoff> — <onde retomar>; git: <limpo|pendente> — <último commit/ação>.`

Não recomende capacidade acima da necessária.