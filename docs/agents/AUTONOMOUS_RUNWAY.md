# Execução autônoma contínua

## Quando carregar

Carregue este arquivo quando a tarefa envolver backlog, fila de issues, plano de
execução, múltiplas frentes, bloqueios, subagentes, continuidade longa ou pedido
para continuar sem interromper a cada etapa.

## Princípio

O orquestrador deve avançar todo trabalho delimitado, autorizado e desbloqueado
até bloqueio real. Checkpoints, commits, comentários e atualizações de ledger são
memória incremental, não sinais de parada.

## Estados da fila

| Estado | Significado | Ação |
| --- | --- | --- |
| `Ready` | Delimitado, autorizado, com aceite e sem bloqueio. | Executar. |
| `Blocked-human` | Precisa de decisão ou validação humana. | Registrar e procurar outro `Ready`; parar só se bloquear tudo. |
| `Blocked-technical` | Precisa de evidência, teste, ambiente ou correção predecessora. | Resolver se estiver no escopo; caso contrário registrar. |
| `Out-of-scope` | Não autorizado pela issue/plano atual. | Não executar. |
| `Parallelizable` | Independente e delegável. | Delegar com contexto mínimo e aceite claro. |
| `Sequential` | Depende de outra tarefa. | Aguardar a dependência. |
| `Done` | Aceite verificado, evidência publicada e memória sincronizada. | Reavaliar dependentes. |

## Regra de avanço

1. identificar a fila por issue, epic, plano, ledger, runway e estado Git;
2. classificar cada item;
3. executar todos os `Ready` dentro da autorização;
4. para cada bloqueio, procurar frente independente;
5. publicar checkpoints recuperáveis;
6. reavaliar dependências e fila após cada checkpoint;
7. parar somente quando não houver ação segura ou houver bloqueio humano global.

## Uso de subagentes

Delegue investigação independente, inventário, revisão paralela, testes/logs ou
leitura de módulos distintos. Não use subagentes para escrita concorrente nos
mesmos arquivos.

Cada pacote deve conter:

- objetivo fechado;
- arquivos-alvo;
- ferramentas/comandos permitidos;
- critérios de saída;
- limite de escopo e verbosidade.

O retorno deve trazer achados destilados, evidências, riscos e próximos passos,
não logs brutos.

## Parada proporcional

Pare somente quando:

- decisão humana bloqueia todas as ações úteis;
- continuar ampliaria escopo;
- há risco relevante de produto, segurança, dados ou perda de trabalho;
- faltam critérios de aceite para qualquer ação segura;
- não há mais `Ready` autorizado.

Não pare apenas porque uma microetapa, commit ou issue terminou.

## Estado de domínios específicos

Este arquivo define o mecanismo geral e não mantém estado datado de subsistemas.

Para TTS:

- estado curto: `docs/tts/CURRENT_RUNWAY.md`;
- DAG/fila: `docs/tts/ISSUE_EXECUTION_PLAN.md`;
- evidência/histórico: `docs/tts/EXECUTION_STATUS.md`;
- unidade executável: issue ativa;
- contrato de RenderPlan: `docs/tts/RENDERPLAN_CONTRACT.md`.

O estado de TTS não deve ser copiado novamente para este arquivo.