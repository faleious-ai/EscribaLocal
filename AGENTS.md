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
4. inspecione `git status --short --branch` quando houver ambiente local
   disponível;
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
| Fila de tarefas, backlog, múltiplas frentes, bloqueios ou execução contínua | `docs/agents/AUTONOMOUS_RUNWAY.md` |
| Issue, commit, push, branch, autonomia ou ação remota no GitHub | `docs/agents/AUTONOMY_AND_GIT.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md` |
| Tarefa não trivial ou escolha de skill | `docs/agents/SKILL_ROUTING.md` |
| Escolha de modelo, esforço, orquestrador ou subagentes | `docs/agents/MODEL_ROUTING.md` |
| Tarefa de domínio, produto ou TTS | `CONTEXT.md`, depois documentos indicados por ele |
| TTS atual | `docs/tts/EXECUTION_STATUS.md`, `docs/tts/ISSUE_EXECUTION_PLAN.md` e issue ativa |
| Arquitetura ou decisão técnica | ADRs relevantes em `docs/adr/` |
| Ambiente das skills | `docs/agents/skills-runtime.md` |

## Contexto de domínio

Este é um repositório de contexto único. Antes de planejar ou modificar
comportamento não trivial de domínio/produto, leia `CONTEXT.md` e siga a ordem de
precedência definida ali.

Para o subsistema TTS, `CONTEXT.md` aponta as fontes de verdade vigentes. Não
trate PRDs e prompts históricos como escopo ativo quando divergirem do escopo
consolidado atual.

Não pergunte ao usuário algo que possa ser descoberto examinando o repositório.

## Execução autônoma contínua

Protocolo rígido: o orquestrador deve seguir este `AGENTS.md` e executar
continuamente todo trabalho delimitado, autorizado e desbloqueado. Checkpoint,
commit, push, comentário em issue, fechamento de issue ou conclusão de uma
microtarefa **não são motivos para parar**.

Enquanto houver tarefa agendada em issue, plano, ledger ou fila que seja segura,
delimitada e autorizada, o orquestrador deve reavaliar a fila e continuar pela
próxima tarefa. Só pode encerrar a rodada quando o trabalho tiver realmente
terminado ou quando um bloqueio humano impedir todas as próximas ações úteis.

Enquanto a fila tiver qualquer item `Ready`, o agente **não deve enviar resposta
final, resumo de status, recomendação de próxima execução nem devolver o turno ao
usuário**. Deve manter o loop de trabalho: executar → validar → publicar
checkpoint → reavaliar a fila → executar o próximo item. Uma resposta final só é
permitida com fila `empty` ou `blocked-human` para todas as ações úteis.

Um bloqueio humano existe somente quando falta uma decisão, aprovação, acesso ou
validação que não possa ser descoberta nem resolvida com segurança no repositório.
Ele não impede o avanço de frentes independentes prontas.

Quando houver bloqueio humano, a resposta deve conter uma seção visualmente
destacada intitulada `**BLOQUEIO HUMANO**`, informando de forma objetiva:

* o que a pessoa precisa fazer;
* as opções concretas disponíveis;
* a recomendação do agente e a consequência de cada opção;
* quais tarefas continuam executáveis enquanto a decisão não chega.

Não peça continuação, confirmação genérica ou autorização já concedida por este
arquivo. Não pare apenas porque uma etapa foi publicada.

## Roteamento obrigatório de skills

Antes de planejar, editar arquivos ou executar mudanças, classifique a tarefa e
use explicitamente a skill instalada mais apropriada. Para tarefas não triviais,
carregue `docs/agents/SKILL_ROUTING.md`.

Informe no início da resposta:

`Roteamento: $nome-da-skill — motivo`

Quando a tarefa for realmente trivial:

`Roteamento: execução direta — tarefa trivial e completamente especificada`

Use apenas skills realmente instaladas. Nunca afirme ter usado uma skill que não
foi carregada.

## Modelos, esforço e subagentes

A política normativa do ambiente Codex está em
`docs/agents/MODEL_ROUTING.md`. Use os nomes exatos da interface:

* modelos: `5.6 Sol`, `5.6 Terra`, `5.6 Luna`, `5.5`, `5.4` e `5.4 Mini`;
* esforços: `Leve`, `Médio`, `Alto`, `Extra alto` e `Ultra`.

Regra permanente: use o menor orquestrador, menor esforço e menores subagentes
suficientes para entregar com segurança, evidência, validação e qualidade
aceitável. Não use o modelo mais forte, esforço alto ou `Ultra` como padrão.

## GitHub como memória recuperável

O GitHub é a fonte primária de continuidade. Ao final de qualquer rodada não
trivial, o estado recuperável deve estar no repositório por commits, issues,
ledgers, planos ou documentos de status.

Se houve progresso útil, faça commit e push em `main`, respeitando
`docs/agents/AUTONOMY_AND_GIT.md`. Se a rodada não puder ser publicada, explique
o bloqueio e registre a continuidade em issue, ledger ou documento de status.
Não deixe a memória da tarefa depender apenas do chat.

`$handoff` é exceção: use somente quando a continuidade necessária ainda não
estiver suficientemente persistida no repositório e não puder ser persistida
antes do encerramento.

## Proteções críticas

* Inspecione `git status` antes de editar quando houver ambiente local.
* Não descarte nem sobrescreva alterações existentes do usuário.
* Não amplie o escopo sem autorização.
* Não reescreva a aplicação quando uma alteração incremental for viável.
* Não exponha nem modifique segredos ou credenciais reais.
* Para issues delimitadas, siga `docs/agents/AUTONOMY_AND_GIT.md` e conclua
  autonomamente commits, push e atualizações remotas necessárias.
* Fora desses limites, obtenha decisão explícita do usuário.
* Execute testes e verificações relevantes antes de declarar o trabalho concluído.
* Revise o diff final e informe verificações que não puderam ser executadas.

## Recomendação final obrigatória

Ao concluir uma etapa ou recomendar continuidade, use o formato:

`Próxima execução: orquestrador <Modelo>, esforço <Leve|Médio|Alto|Extra alto|Ultra>; fila <ready|blocked|empty>: <resumo>; subagentes <nenhum|lista modelo/esforço/função>; decisão humana <não|sim — motivo>; suficiência: <motivo curto>; limite: <restrição de contexto/tokens/escopo>; continuidade: <persistida|requer handoff> — <onde retomar>; git: <limpo|pendente> — <último commit/ação>.`

Não recomende capacidade acima da necessária. Quando a tarefa seguinte for
pequena, mecânica e diretamente validável, prefira `5.6 Luna` ou `5.4 Mini` com
esforço `Leve`.
