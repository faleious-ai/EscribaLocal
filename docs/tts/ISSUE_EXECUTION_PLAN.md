# TTS Issue Execution Plan

Data: 2026-07-10

## Objetivo desta rodada

Registrar uma revisão documental e de governança do subsistema TTS para
evitar execução improvisada de tarefas e reduzir fuga de escopo antes de
novas implementações.

Atualização desta rodada:

- o plano permanece alinhado ao escopo consolidado;
- o ledger de `T2.1` e `T2.2` deve refletir estado real publicado, não apenas
  a última base histórica do Gate B;
- os textos prontos de issues e comentários ficam centralizados em
  `docs/tts/ISSUE_DRAFTS.md`.

## Base operacional da revisão

- Base de comparação operacional: `origin/main`
- HEAD local na rodada: `addfaa5b7b9009b40ca608302853328724deb9f2`
- `origin/main` na rodada: `addfaa5b7b9009b40ca608302853328724deb9f2`
- Diferença de commits `origin/main..HEAD`: nenhuma

## Precedência adotada

1. instrução explícita mais recente do usuário;
2. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`;
3. `docs/tts/EXECUTION_STATUS.md`;
4. relatório do gate atual;
5. ADRs compatíveis;
6. `AGENTS.md` e docs operacionais;
7. `PROMPT_MESTRE_TTS_ESCRIBALOCAL.md` apenas como histórico;
8. `CODEX_CONTINUIDADE_GATE_A_PARA_REVISAO.md` apenas como continuidade histórica do Gate A.

## Classificação documental

| Documento | Classificação | Uso nesta rodada |
| --- | --- | --- |
| `AGENTS.md` | operacional vigente | regras de trabalho, skill routing, proteções e regime Git |
| `CONTEXT.md` | índice de precedência do domínio | confirma ordem de leitura e natureza histórica da PRD antiga |
| `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md` | escopo consolidado ativo | fonte principal para gates, tarefas e critérios de aceite |
| `docs/tts/EXECUTION_STATUS.md` | ledger operacional ativo | fonte de verdade do progresso auditável |
| `docs/tts/gate-a-report.md` | relatório histórico válido do Gate A | evidência de fechamento do Gate A |
| `PROMPT_MESTRE_TTS_ESCRIBALOCAL.md` | histórico / PRD anterior | contexto de origem; não limita o escopo atual |
| `CODEX_CONTINUIDADE_GATE_A_PARA_REVISAO.md` | histórico / governança do Gate A | útil para auditar Gate A; não governa Gate B |
| `docs/adr/0001-isolar-vibevoice-realtime-por-subprocesso.md` | ADR aceito e compatível | governa apenas a estratégia do Realtime 0.5B |
| `docs/agents/issue-tracker.md` | operacional | convenções para issues no GitHub |
| `docs/agents/triage-labels.md` | operacional | significado dos labels canônicos |
| `docs/agents/skills-runtime.md` | operacional | lembra que skills vivem no ambiente, não no repo |
| `docs/agents/domain.md` | operacional leve | reforça leitura de `CONTEXT.md`, ADRs e docs |

## Inventário atual de issues

Issues abertas na rodada:

- `#1` `PRD: TTS local verificavel com VibeVoice e Chatterbox PT-BR`
- `#8` `HITL: Decidir estrategia nativa do Realtime 0.5B`
- `#12` `AFK: Validar exemplos reais e relatorio final de TTS local`

Issues históricas fechadas relevantes:

- `#2` remover fallbacks SAPI5 e tom
- `#3` estados explícitos e conversão do VibeVoice 1.5B
- `#4` exigir voz real para gerar TTS
- `#5` bloquear Realtime até geração nativa real
- `#6` preservar Large com erro claro
- `#7` adicionar etapa "Criar sua voz" na primeira execução
- `#9` criar orchestration de TTS para tags, PT-BR e segmentos
- `#10` adicionar Chatterbox ao catálogo sem execução
- `#11` implementar adapter local Chatterbox PT-BR
- `#13` criar worker isolado para tracer bullet do Realtime 0.5B

## Diagnóstico de governança

1. O tracker aberto está subdimensionado em relação ao plano consolidado atual.
2. O ledger e o código já avançaram pelo Gate B, mas quase todo esse avanço está
   sem issue própria clara.
3. Existem issues fechadas históricas com escopo mais amplo do que a entrega real
   observável no código atual.
4. O ledger está funcional como fonte de progresso, mas está desatualizado em
   relação ao estado real publicado do T2.2.
5. O trabalho recente de T2.2 foi tecnicamente incremental e dentro do domínio
   correto, mas foi executado sem issue formal correspondente no tracker atual.

## Tabela issue -> estado real

| Issue | Tipo atual | Relação com escopo consolidado | Estado real observado |
| --- | --- | --- | --- |
| `#1` | PRD histórica aberta | documento de origem, hoje insuficiente como plano executivo | manter como guarda-chuva histórico; não é issue executável |
| `#8` | HITL aberta | alinhada ao ADR `0001` e ao T10.2/T10.3 | continua válida; bloqueia somente a retomada do Realtime nativo |
| `#12` | AFK aberta | alinhada ao fim do plano (`T14.4`/`T14.5`) | continua válida, mas depende de várias tarefas ainda não rastreadas no tracker |
| `#7` | fechada histórica | corresponde parcialmente a `T3.1` | fechamento parece prematuro: há etapa informativa no wizard, mas não um fluxo completo de captura/importação/aprovação |
| `#9` | fechada histórica | cobre parte de `T4.x`, `T5.1`, `T6.x`, `T7.1` | fechamento parece amplo demais: o código atual ainda usa parser simples com `[style:...]`, sem AST formal, sem subtítulos, sem eventos, sem RenderPlan e sem AudioAssembler |

## Tabela gate/task -> issue

| Gate / Task | Issue correspondente atual | Observação |
| --- | --- | --- |
| `T0.1`, `T0.2`, `T1.1`, `T1.2`, `T1.3`, `T9.3`, `T10.1` | histórico disperso em `#1`, `#2`, `#5`, `#6`, `#13` | Gate A auditável e coerente |
| `T2.1` | sem issue clara | implementado e verificado no ledger; precisa rastreio histórico mínimo |
| `T2.2` | `#16` | verificada no ledger e fechada como concluída |
| `T2.3` | `#17` | triada como `ready-for-agent`; implementação e testes concluídos localmente, aguardando publicação e fechamento |
| `T2.4` | sem issue clara | parcialmente coberta por capabilities de import/export de voz, mas não por pacote versionado completo com estilos/eventos |
| `T3.1` | `#7` (parcial / insuficiente) | issue fechada não cobre todo o aceite do escopo consolidado |
| `T3.2`, `T3.3` | sem issue clara | ainda não rastreadas |
| `T4.1` | sem issue clara | ainda não rastreada |
| `T4.2` | `#9` (parcial / insuficiente) | implementação atual cobre só parte do objetivo |
| `T4.3` | sem issue clara | ainda não rastreada |
| `T5.1`, `T5.2`, `T7.1` | `#9` (insuficiente) | issue histórica ampla demais para o estado real |
| `T6.1` | `#9` (parcial) | existe normalização inicial, mas não o módulo completo previsto no escopo |
| `T8.x` | `#10`, `#11` | ainda precisam conferência mais profunda antes de serem tratadas como totalmente alinhadas ao escopo consolidado |
| `T10.2`, `T10.3` | `#8` + `#13` | dependem da decisão humana e do ADR |
| `T14.4`, `T14.5` | `#12` | issue final continua válida |

## Trabalho inicialmente implementado sem issue clara (diagnóstico histórico)

- `T2.1` schema de voz v2 em `services/voice_profiles.py`
- `T2.2` backend/API de estilos:
  - CRUD de estilos
  - `style_id` estável com rename do nome visível
  - ordem e ativação
  - `instruction`
  - `parameters`
  - `engine_compatibility`
  - referência opcional normalizada por estilo
  - remoção da referência
  - leitura de mídia original e normalizada por HTTP

O desvio de rastreio de `T2.2` foi resolvido pela issue `#16`. `T2.3` foi
formalizada antes da implementação na issue `#17`.

## Trabalho já resolvido pelo código mas mal representado no tracker

- Gate A no geral está melhor representado pelo ledger do que pelas issues históricas.
- `T2.1` permanece sem issue histórica dedicada.
- `T2.2` foi reconciliada com a issue `#16`, evidências publicadas e fechamento.
- `T2.3` está rastreada pela issue `#17` desde antes da implementação.

## Issues amplas demais ou desalinhadas

- `#1`: ampla demais para execução; deve permanecer como PRD histórica e não como fila operacional.
- `#7`: fechada cedo demais para o aceite atual de `T3.1`.
- `#9`: fechada cedo demais para o aceite atual de `T4.1`, `T4.2`, `T5.1`, `T6.1` e `T7.1`.
- `#12`: válida, mas muito distante da próxima execução operacional.

## Issues bloqueadas

- `#8`: bloqueada apenas por `#5` no texto, mas no escopo consolidado também está
  logicamente limitada pelo ADR `0001`.
- `#12`: efetivamente bloqueada por lacunas relevantes dos Gates B, C, D, E e pela
  decisão HITL do Realtime.

## Issues que precisam de decisão humana

- `#8`: decidir estratégia nativa do Realtime 0.5B conforme ADR `0001`.
- Reabertura ou substituição funcional de `#7` e `#9`: decisão de governança do
  tracker, não técnica do runtime.

## Verificação específica do T2.2

Checagem contra o aceite documentado:

- criar: atendido
- duplicar: atendido
- renomear mantendo `style_id`: atendido
- editar: atendido
- ordenar: atendido
- ativar/desativar: atendido
- excluir: atendido
- `style_id` estável: atendido
- nome visível mutável: atendido
- referência opcional: atendido
- exclusão do estilo não apaga a voz: atendido

Itens avaliados e classificados fora do aceite de `T2.2`/`#16`:

- preview por engine real exige rastreio futuro próprio
- UI completa de gerenciamento de estilos exige decisão e issue próprias
- capability matrix operacional pertence a uma tarefa posterior

Esses itens não devem ser tratados como pendências implícitas de `#16`.

## Evidências operacionais de T2.2

Estas subfatias integram o checklist/evidência da issue `#16` e não geram
microissues separadas:

- persistência de `instruction`
- persistência de `parameters`
- `DELETE` da referência de estilo
- `GET` da mídia original de estilo
- duplicação da referência normalizada e do original junto com o estilo
- falha explícita e sem cópia órfã quando a referência marcada como pronta está
  incompleta
- remoção da cópia criada e ressincronização do perfil quando a primeira ou a
  segunda escrita de mídia falha; falha do próprio rollback permanece explícita

Tratamento recomendado:

- não abrir issue separada para cada uma;
- registrar tudo como checklist de evidências dentro da issue `#16`;
- manter o ledger alinhado aos commits `03e28743`/`ff81eb75` e ao fechamento da
  issue `#16`.

## T2.2 encerrada e T2.3 em conclusão

Issue concluída:

- `#16` `AFK: Formalizar e concluir T2.2 da entidade Style` — fechada como
  `completed` após sincronização de aceite, testes e evidências.

Issue operacional atual:

- `#17` `AFK: Implementar T2.3 da entidade Event` — triada como
  `ready-for-agent`; implementação e suíte completa concluídas localmente em
  2026-07-10. Restam publicação, sincronização das evidências e fechamento.

Atualização do tracker em 2026-07-09:

- `#16` fechada como `completed`
- `#17` criada como `needs-triage`; posteriormente triada para `ready-for-agent`
- `#18` `AFK: Implementar T3.1 de captura real da primeira voz no wizard`

## Ordem operacional recomendada

1. `T2.2 — Formalizar e concluir entidade Style` — concluída
2. `T2.3 — Implementar entidade Event` — em conclusão pela issue `#17`
3. `T3.1 — Captura real da primeira voz no wizard` — próxima candidata, somente após fechar `#17` e triar `#18`
4. proposta de divisão `T4.x / T5.x / T6.x / T7.x`

Regra de governança:

- não puxar `T4.x` ou posterior antes de concluir `T2.3` e formalizar a ordem de
  execução posterior;
- não tratar `#12` como próxima execução operacional;
- não deixar subfatias de `Style` nascerem fora da issue dedicada.

## Ações recomendadas no tracker

### Fechadas

- `#16` — aceite e evidências consolidados; fechada como `completed`

### Em conclusão

- `#17` — implementação e testes locais concluídos; aguarda commit publicado,
  checklist/evidências no tracker e fechamento

### Dividir

- substituir a cobertura ampla de `#9` por novas fatias específicas de `T4.x`,
  `T5.1`, `T6.x` e `T7.1`

### Bloquear

- manter `#8` como HITL bloqueando apenas Realtime nativo
- manter `#12` bloqueada por lacunas restantes do plano

### Atualizar

- `#1` com comentário explicitando que é PRD histórica e que o plano operacional
  vigente está em `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md` e
  `docs/tts/EXECUTION_STATUS.md`
- `#12` com comentário atualizando dependências reais e deixando explícito que os
  Gates B-E ainda não estão concluídos

### Manter

- `#8` aberta como decisão humana

## Texto sugerido para comentário em `#1` (não publicado)

```text
Esta issue permanece como PRD histórica do TTS, mas não deve mais ser usada como fila operacional única. A fonte de verdade atual para escopo e precedência é `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`, e o progresso auditável vigente está em `docs/tts/EXECUTION_STATUS.md`.

O trabalho já publicado em `main` fechou o Gate A e avançou pelo Gate B (`T2.1` verificado e `T2.2` em progresso real no código), mas esse avanço não está refletido em issues granulares suficientes no tracker. Próximo passo de governança recomendado: abrir issues novas por tarefa/gate do plano consolidado, começando por `T2.2`.
```

## Texto sugerido para comentário em `#12` (não publicado)

```text
Revisão de governança em `origin/main`: a issue continua válida como etapa final de validação/relatório, mas hoje ela está mais distante do estado real do plano consolidado do que o tracker sugere.

Gate A está fechado no ledger. Em Gate B, `T2.1` já está verificado e `T2.2` está em progresso real no código publicado, porém ainda faltam tarefas não rastreadas formalmente no tracker, incluindo conclusão de `T2.2`, `T2.3`, `T3.x` e os blocos de parser/orquestração/renderização. Também permanece aberta a decisão HITL de Realtime em `#8`.

Antes de tratar esta issue como próxima executável, recomenda-se formalizar novas issues operacionais alinhadas ao escopo consolidado atual.
```

## Registro histórico do texto usado para a issue `#16`

```text
## Parent

https://github.com/faleious-ai/EscribaLocal/issues/1

## What to build

Formalizar e concluir a entidade `Style` dentro de cada voz, consolidando o que já existe no backend/API e fechando as pendências restantes do aceite do Gate B sem avançar para parser, RenderPlan ou eventos.

## Acceptance criteria

- [ ] CRUD de estilos permanece coberto por testes de ponta a ponta
- [ ] `style_id` continua estável mesmo com rename do nome visível
- [ ] referência opcional de estilo continua normalizada e persistida com mídia original e derivada
- [ ] ledger registra `03e28743` como publicado e separa validação local posterior
- [ ] pendências restantes de `T2.2` ficam explicitadas sem misturar `T2.3` ou `T4.x`

## Blocked by

None - can start immediately
```

## Texto publicado na issue `#16`

Comentário: https://github.com/faleious-ai/EscribaLocal/issues/16#issuecomment-4930885411

```text
T2.2 está implementado em `main` pelo commit `03e28743`.

Evidências consolidadas:
- CRUD de estilos persistidos em `style.json` e sincronizados em `profile.json`;
- `style_id` estável com rename do nome visível;
- criar, duplicar, editar, ordenar, ativar/desativar e excluir cobertos por testes;
- referência opcional com original e derivada, incluindo limpeza e leitura HTTP;
- duplicação preserva metadados e copia `reference.wav` e `original.wav`;
- mídia marcada como pronta mas incompleta falha antes de criar a cópia;
- falha na primeira ou segunda cópia de mídia remove a cópia criada e ressincroniza o perfil; falha do rollback é reportada explicitamente.

Validação local posterior ao commit: `python -m pytest -q` -> `236 passed`, `4 warnings` conhecidas de `FastAPI.on_event`.

Fora de T2.2/#16: preview por engine real, UI completa de estilos, Event, parser/AST, RenderPlan, AudioAssembler, timeline, wizard e capability matrix operacional.

Concluído: validação publicada em `ff81eb75`, checklist/evidências sincronizados e issue fechada como `completed`.
```
