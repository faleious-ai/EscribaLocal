# Autonomia, Git e memória recuperável

## Quando carregar

Carregue este arquivo quando a tarefa envolver issue, alteração de arquivos,
commit, push, atualização remota no GitHub, dúvida sobre autonomia, branch,
escopo, publicação, continuidade ou estado local.

## Regime de trabalho Git

Decisão operacional vigente: todo trabalho deve acontecer diretamente em `main`.
Não crie branches de trabalho, branches `codex/*` ou branches paralelas sem uma
instrução explícita posterior do usuário revogando esta decisão.

Se encontrar trabalho em outra branch, consolide-o em `main` antes de continuar,
preservando alterações locais e sem descartar commits. Depois da consolidação
local, remova a branch paralela local quando ela não for mais necessária.

## Autorização permanente para issues delimitadas

O usuário autoriza permanentemente o agente a realizar, sem pedir ou aguardar
nova confirmação, todas as ações necessárias para concluir uma issue delimitada
deste repositório.

Uma issue está delimitada quando:

* pertence a `faleious-ai/EscribaLocal` e está identificada por número ou título;
* possui objetivo, escopo, fora de escopo, critérios de aceite e critério de
  parada claros na própria issue ou nos documentos de precedência do projeto;
* está `ready-for-agent` ou foi escolhida explicitamente pelo usuário;
* não depende de decisão humana pendente, informação ausente ou ampliação de
  escopo.

Dentro desses limites, estão previamente autorizados:

* leitura, edição, testes, instalação de dependências necessárias e atualização
  de documentação, ledger e planos;
* commits e push diretamente em `main`;
* comentários, edição, labels, fechamento ou reabertura de GitHub Issues;
* outras alterações remotas no próprio repositório exigidas pelo aceite;
* tag, release ou deploy somente quando forem requisitos explícitos da issue.

A autorização não permite criar branches, ampliar o escopo, reescrever histórico,
usar comandos Git destrutivos, apagar dados não pertencentes à issue, modificar
segredos reais ou atuar em sistemas externos que não estejam explicitamente no
escopo. Issues `ready-for-human`, `needs-info`, `needs-triage` ou bloqueadas por
decisão humana exigem resolver esse estado antes da execução autônoma.

O agente deve executar testes e revisão proporcionais ao risco, registrar
evidências no tracker/ledger, respeitar o critério de parada e relatar as ações
remotas depois de concluí-las; não deve interromper o fluxo apenas para pedir
autorização já concedida por este protocolo.

## GitHub como memória recuperável

O GitHub é a fonte primária de continuidade. O chat não deve ser a única memória
do trabalho.

Toda etapa não trivial deve terminar com estado persistido no repositório. Sempre
que uma etapa gerar mudança útil e coerente, faça commit pequeno, descritivo e,
quando aplicável, vinculado à issue. Ao fim de cada rodada, o trabalho atual deve
estar commitado e publicado em `main`, salvo bloqueio técnico explícito.

Atualize issue, ledger, plano ou documento de status junto com o código quando
isso for necessário para reconstruir a continuidade. Não deixe decisões,
progresso, pendências ou critérios de retomada apenas no chat.

Antes de encerrar a rodada, rode `git status --short --branch` quando houver
ambiente local disponível e informe se o working tree ficou limpo ou por que não
ficou. Quando a rodada for executada diretamente pela API do GitHub, informe o
commit publicado e a limitação de não haver working tree local inspecionável.

## Checkpoints de etapa

Uma etapa pode ser atualização documental de governança, triagem de issue,
criação ou ajuste de plano, teste novo, implementação de fatia vertical,
correção de bug, atualização de ledger/status, comentário ou fechamento de issue,
ou revisão final.

Cada etapa deve gerar um commit quando produzir alteração persistente relevante.
Os commits devem ser pequenos o suficiente para revisão, descritivos,
preferencialmente verdes, acompanhados de testes proporcionais ao risco e sem
misturar tarefas independentes.

## Commits vermelhos

Não use commit vermelho em `main` como padrão.

Um commit vermelho só é aceitável quando:

* for uma etapa TDD deliberada;
* a falha estiver isolada e documentada;
* o commit deixar claro que é um checkpoint RED;
* a próxima etapa imediata for implementar o GREEN;
* o usuário tiver autorizado esse padrão para a tarefa.

Caso contrário, commits publicados em `main` devem preservar estado executável
ou, no mínimo, documentar claramente a limitação.

## Exceções de publicação

Se não for possível commit/push, registre o motivo, estado local, arquivos
afetados, testes/verificações executados e próximo passo seguro. Antes de gerar
`$handoff`, prefira persistir a continuidade em issue, ledger, plano ou documento
de status.
