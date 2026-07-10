# GitHub Project setup — TTS Governed Delivery

Status: configuração pendente por limitação do conector usado na rodada de governança.

O conector permitiu arquivos, issues, comentários, labels e reabertura, mas não
expôs criação de Project, milestone, sub-issues ou dependências nativas. Este
arquivo preserva a configuração exata para execução posterior por UI ou `gh` com
permissões adequadas.

## Project

Nome: `EscribaLocal — TTS Governed Delivery`

## Campos

| Campo | Valores |
| --- | --- |
| Status | Backlog, Ready, In progress, Review, Blocked-human, Blocked-technical, Done |
| Gate | A, B, C, D, E, F |
| Task ID | texto curto, ex.: T5.1 |
| Priority | P0, P1, P2 |
| Type | Epic, Task, Decision, Defect, Validation |
| Execution mode | AFK, HITL |
| Evidence | Missing, Partial, Complete |
| Last checkpoint | data |

## Views

### Runway

Board agrupado por `Status`.

### Current Gate

Tabela filtrada por `Gate = C`, mostrando Task ID, Status, Priority, Evidence e
Last checkpoint.

### Blocked

Filtro: `Status = Blocked-human OR Status = Blocked-technical`.

### Human decisions

Filtro: `Execution mode = HITL`.

### Evidence gaps

Filtro: `Status = Done AND Evidence != Complete`.

### Roadmap

Agrupar por Gate; não criar datas artificiais.

## Milestone

Nome: `TTS Gate C — Linguagem, validação e RenderPlan`

Itens:

- #21;
- #22;
- #23;
- #24;
- #25;
- #26.

## Hierarquia

Epic pai: #26

Sub-issues desejadas:

- #21;
- #22;
- #23;
- #24;
- #25.

## Dependências nativas desejadas

```text
#22 blocked by #21
#23 blocked by #22
#24 blocked by #23
#25 blocked by #24
```

## Estado inicial dos itens

| Issue | Status | Gate | Task ID | Type | Mode | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| #26 | In progress | C | Gate C | Epic | AFK | Partial |
| #21 | Done | C | T4.1 | Task | AFK | Complete |
| #22 | Done | C | T4.2 | Task | AFK | Complete |
| #23 | Done | C | T4.3 | Task | AFK | Complete |
| #24 | Ready | C | T5.1 | Defect/Task | AFK | Partial |
| #25 | Blocked-technical | C | T5.2 | Task | AFK | Missing |
| #8 | Blocked-human | F | T10.2/T10.3 | Decision | HITL | Missing |
| #12 | Backlog | F | T14.4/T14.5 | Validation | AFK | Missing |

## Automações seguras

- item novo → Backlog;
- issue fechada → Done;
- issue reaberta → In progress;
- auto-add das issues do repositório;
- arquivar itens concluídos antigos somente após janela definida.

Não automatizar `Ready` apenas porque a issue existe. Prontidão exige contrato e
dependências concluídas.

## Critério de conclusão desta configuração

- Project criado;
- campos e views configurados;
- milestone criado;
- #21–#26 adicionadas;
- sub-issues e dependências nativas registradas;
- links do Project/milestone adicionados a #26 e `CURRENT_RUNWAY.md`;
- este arquivo atualizado de `pendente` para `concluído`.