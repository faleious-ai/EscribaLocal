# Autonomia, Git e memória recuperável

## Quando carregar

Carregue quando a tarefa envolver issue, alteração de arquivos, commit, push,
atualização remota, autonomia, branch, escopo, publicação ou continuidade.

## Regime de trabalho Git

Todo trabalho ocorre diretamente em `main`. Não crie branches de trabalho sem
instrução explícita posterior do usuário.

Se encontrar trabalho em outra branch, consolide-o em `main` preservando commits e
alterações locais. Não use comandos destrutivos nem reescreva histórico.

## Autorização permanente para issues delimitadas

O usuário autoriza o agente a concluir, sem nova confirmação, issues delimitadas
de `faleious-ai/EscribaLocal` que possuam objetivo, escopo, fora de escopo, aceite
e parada claros, estejam `ready-for-agent` ou tenham sido escolhidas
explicitamente e não dependam de decisão humana pendente.

Dentro desses limites, estão autorizados:

- leitura, edição, testes e dependências necessárias;
- atualização de documentação, ledger, planos e runway;
- commits e push em `main`;
- comentários, edição, labels, fechamento ou reabertura de issues;
- outras alterações remotas exigidas pelo aceite.

Não estão autorizados sem decisão explícita:

- ampliar escopo;
- criar branches;
- reescrever histórico;
- apagar dados alheios à issue;
- modificar segredos;
- atuar em sistemas externos não previstos;
- criar tag, release ou deploy sem requisito explícito.

## GitHub como memória recuperável

Toda etapa não trivial termina com estado persistido no repo. Faça commits
pequenos, descritivos e preferencialmente verdes. Atualize issue, ledger, plano ou
runway quando necessário para reconstruir continuidade.

Antes de encerrar, rode `git status --short --branch` quando houver ambiente local.
Em execução pela API do GitHub, informe o commit e a limitação de não haver working
tree local inspecionável.

## Checkpoints sem interrupção

Commit/push não encerra a rodada. Depois de cada checkpoint:

1. registrar evidência na issue quando aplicável;
2. atualizar memória operacional se o estado mudou;
3. reavaliar dependentes e fila;
4. continuar se houver item `Ready`.

## Gate obrigatório de fechamento de issue

Uma issue só pode ser fechada quando:

- todos os critérios de aceite estão explicitamente avaliados;
- cada critério aponta para teste, diff, documento, comando ou outra evidência;
- testes/verificações proporcionais ao risco foram executados;
- limitações e verificações impossíveis foram registradas;
- commits relevantes estão publicados;
- ledger/status foi atualizado quando aplicável;
- runway/plano foi atualizado se a fila mudou;
- dependentes foram retriados;
- o comentário final contém o mapa `aceite → evidência`.

Suíte verde isolada não prova critérios não cobertos. Não feche uma issue apenas
porque um teste existente passou ou porque a implementação parece plausível.

Formato recomendado do comentário final:

```text
## Evidência de fechamento
- Commit(s):
- Testes/verificações:
- Critério 1 → evidência:
- Critério 2 → evidência:
- Limitações:
- Ledger/runway atualizados:
- Dependentes retriados:
```

## Reabertura por aceite incompleto

Se auditoria posterior demonstrar que um critério explícito não foi entregue ou
não possui evidência suficiente, o agente está autorizado a:

1. reabrir a issue;
2. registrar a lacuna objetivamente;
3. corrigir ledger/runway;
4. bloquear dependentes;
5. executar a correção somente quando a issue estiver novamente delimitada e
   pronta.

Reabrir não apaga o trabalho já entregue; distingue entrega parcial de aceite
completo.

## Commits vermelhos

Não publique commit vermelho em `main` como padrão. Só é aceitável em TDD
deliberado, isolado, documentado e com próxima etapa GREEN imediata autorizada.

## Exceções de publicação

Se não for possível commit/push, registre motivo, estado local, arquivos afetados,
verificações e próximo passo seguro. Antes de `$handoff`, prefira persistir em
issue, ledger, plano ou runway.