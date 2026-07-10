# Execução autônoma contínua

## Quando carregar

Carregue este arquivo quando a tarefa envolver backlog, fila de issues, plano de
execução, múltiplas frentes, bloqueios, subagentes, continuidade longa ou pedido
para “continuar” sem interromper a cada etapa.

## Princípio

O orquestrador deve avançar todo trabalho delimitado, autorizado e desbloqueado
até atingir bloqueio real. Não deve parar após cada microtarefa apenas para pedir
continuação.

Checkpoints, commits, comentários em issue e atualizações de ledger são memória
incremental, não sinais automáticos de parada. Após publicar um checkpoint, o
orquestrador deve reavaliar a fila e continuar se houver próxima tarefa segura,
delimitada, autorizada e desbloqueada.

## Estados da fila

Use estes estados para classificar trabalho:

| Estado | Significado | Ação |
| --- | --- | --- |
| `Ready` | Tarefa delimitada, autorizada, com aceite e sem bloqueio. | Executar. |
| `Blocked-human` | Precisa de decisão do usuário ou validação humana. | Registrar bloqueio e procurar outro item `Ready`. Só parar se bloquear todas as próximas ações úteis. |
| `Blocked-technical` | Precisa de evidência, teste, ambiente, correção prévia ou recurso técnico. | Resolver se estiver dentro do escopo; caso contrário registrar e procurar outro item `Ready`. |
| `Out-of-scope` | Não autorizado pela issue/plano atual. | Não executar sem nova autorização. |
| `Parallelizable` | Pode avançar de forma independente, normalmente por subagente. | Delegar com contexto mínimo e critérios claros. |
| `Sequential` | Depende da saída de outra tarefa. | Executar somente após a dependência. |

## Regra de avanço

1. Identifique a fila de tarefas aplicável a partir de issue, plano, ledger,
   documentos de status e estado Git.
2. Classifique cada item em `Ready`, `Blocked-human`, `Blocked-technical`,
   `Out-of-scope`, `Parallelizable` ou `Sequential`.
3. Execute todos os itens `Ready` que estejam dentro do escopo e da autorização.
4. Para cada `Blocked-human`, verifique se existe outro item `Ready` ou
   `Parallelizable` independente.
5. Só peça intervenção humana quando não houver mais item `Ready` seguro ou
   quando continuar criaria risco de escopo, produto, segurança ou perda de
   trabalho.
6. Ao fim da rodada, registre no GitHub quais frentes foram concluídas, quais
   ficaram bloqueadas e por quê.

## Uso de subagentes

Subagentes são mecanismo para avançar frentes independentes sem contaminar o
contexto principal. Delegue quando houver investigação independente, leitura de
módulos diferentes, inventário, testes/logs, revisão paralela, preparação de
insumos ou auditoria de partes distintas.

Não use subagentes para escrita concorrente nos mesmos arquivos. Subagentes devem
receber objetivo fechado, arquivos-alvo, comandos permitidos, critérios de saída
e limite de verbosidade. Eles devem retornar achados destilados, evidências,
riscos, conclusões e próximos passos; não logs brutos.

Se um subagente encontrar bloqueio, o orquestrador registra o bloqueio, reconcilia
o impacto e redistribui atenção para outra frente desbloqueada.

## Parada proporcional

Pare somente quando:

* uma decisão humana bloqueia todas as próximas ações úteis;
* continuar ampliaria escopo sem autorização;
* há risco relevante de segurança, produto, dados ou perda de trabalho;
* faltam critérios de aceite para qualquer próxima ação segura;
* não há mais itens `Ready` dentro da autorização atual.

Não pare apenas porque uma microetapa foi concluída, um commit foi publicado ou
um documento foi atualizado.

## Estado atual conhecido do TTS

No estado registrado em 2026-07-10:

* `#18` / `T3.1` e `#19` / `T3.2` estão concluídas;
* `T3.3` é a próxima frente, mas permanece `Blocked-human` até haver uma
  decisão sobre os critérios de derivação e qualidade por engine;
* `#8` é `Blocked-human` para Realtime nativo;
* `#12` está bloqueada por lacunas posteriores e não é próxima execução;
* `T4.x` é `Out-of-scope` até concluir `T3.3` e formalizar a ordem posterior.

Quando esse estado mudar, atualize os documentos de TTS e a issue correspondente.
