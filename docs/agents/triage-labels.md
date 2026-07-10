# Triage Labels

Este repositório usa os cinco rótulos canônicos abaixo, sem mapeamento alternativo.

| Papel canônico | Rótulo no tracker | Significado |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Manter a issue para avaliação ou especificação. |
| `needs-info` | `needs-info` | Aguardando informação do autor. |
| `ready-for-agent` | `ready-for-agent` | Especificada, aceita e sem dependência aberta para um agente assumir. |
| `ready-for-human` | `ready-for-human` | Requer decisão ou execução humana. |
| `wontfix` | `wontfix` | Não será tratada. |

## Regra de prontidão

`ready-for-agent` só pode permanecer quando:

- objetivo, escopo, fora de escopo, aceite e parada estão claros;
- dependências predecessoras estão concluídas;
- não há decisão humana pendente;
- a issue está autorizada para execução.

Se uma predecessora for reaberta, remova `ready-for-agent` dos dependentes e
registre o bloqueio.

## O que não deve virar label

Não criar labels paralelos para `In progress`, `Review`, `Blocked-human`,
`Blocked-technical` ou `Done` apenas para reproduzir workflow. Esses estados ficam
no GitHub Project quando disponível e, na ausência dele, no
`docs/tts/CURRENT_RUNWAY.md`/issue ativa.

Use exatamente os nomes canônicos ao aplicar labels.