# TTS Issue Drafts

Data: 2026-07-07

Este arquivo consolida textos prontos, mas ainda nao publicados, para
atualizacao do tracker do TTS conforme o escopo consolidado atual.

## Comentario proposto para `#1`

```text
Esta issue permanece como PRD historica do TTS, mas nao deve mais ser usada como fila operacional unica. A fonte de verdade atual para escopo e precedencia e `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`, e o progresso auditavel vigente esta em `docs/tts/EXECUTION_STATUS.md`.

O trabalho ja publicado em `main` fechou o Gate A e avancou pelo Gate B (`T2.1` verificado e `T2.2` em progresso real no codigo), mas esse avancoo nao esta refletido em issues granulares suficientes no tracker. Proximo passo de governanca recomendado: abrir issues novas por tarefa/gate do plano consolidado, comecando por `T2.2`.
```

## Comentario proposto para `#8`

```text
Revisao de governanca em `origin/main`: esta issue continua valida como decisao HITL, mas o seu escopo deve permanecer estritamente limitado a `T10.2` e `T10.3`, conforme o ADR `docs/adr/0001-isolar-vibevoice-realtime-por-subprocesso.md`.

Ela nao bloqueia o restante do Gate B nem a formalizacao das tarefas de `Style`, `Event`, `wizard` ou parser/orchestration. O resultado esperado aqui e uma decisao documentada sobre a estrategia nativa do Realtime 0.5B no subprocesso isolado e os criterios minimos para considera-lo realmente disponivel.
```

## Comentario proposto para `#12`

```text
Revisao de governanca em `origin/main`: a issue continua valida como etapa final de validacao/relatorio, mas hoje ela esta mais distante do estado real do plano consolidado do que o tracker sugere.

Gate A esta fechado no ledger. Em Gate B, `T2.1` ja esta verificado e `T2.2` esta em progresso real no codigo publicado, porem ainda faltam tarefas nao rastreadas formalmente no tracker, incluindo conclusao de `T2.2`, `T2.3`, `T3.x` e os blocos de parser/orquestracao/renderizacao. Tambem permanece aberta a decisao HITL de Realtime em `#8`.

Antes de tratar esta issue como proxima executavel, recomenda-se formalizar novas issues operacionais alinhadas ao escopo consolidado atual.
```

## Issue proposta: `T2.2 — Formalizar e concluir entidade Style`

```text
Titulo: AFK: Formalizar e concluir T2.2 da entidade Style

## Parent

https://github.com/faleious-ai/EscribaLocal/issues/1

## Gate / Task

- Gate B
- T2.2 — Implementar entidade Style

## Objetivo

Consolidar a entidade `Style` como unidade persistente da voz, formalizando no tracker o que ja foi entregue em `main` e fechando apenas as pendencias restantes do aceite de `T2.2`, sem misturar `Event`, parser, RenderPlan ou wizard.

## Escopo

- manter o CRUD de estilos persistidos em `style.json`
- manter `style_id` estavel quando o nome visivel mudar
- manter criacao, duplicacao, rename, edicao, ordenacao, ativacao/desativacao e exclusao
- manter referencia opcional por estilo com midia original e derivada
- consolidar `aliases`, `instruction`, `parameters` e `engine_compatibility`
- registrar formalmente no ledger e na issue as subfatias ja entregues
- concluir apenas a superficie restante da entidade `Style`

## Fora de escopo

- entidade `Event`
- parser/AST
- RenderPlan
- AudioAssembler
- timeline
- wizard de captura real
- capability matrix operacional por engine
- UI completa fora do necessario para fechar a superficie de `Style`

## Criterios de aceite

- [ ] criar, duplicar, renomear, editar, ordenar, ativar e excluir estilo seguem cobertos por testes
- [ ] `style_id` permanece estavel mesmo quando o nome visivel muda
- [ ] referencia de estilo continua opcional
- [ ] excluir estilo nao apaga a voz
- [ ] `instruction`, `parameters`, `engine_compatibility` e `aliases` permanecem persistidos e expostos
- [ ] subfatias ja entregues ficam registradas como checklist/evidencia, nao como novas microissues
- [ ] pendencias restantes de `T2.2` ficam explicitadas sem misturar `T2.3` ou `T4.x`

## Checklist de evidencias ja entregues

- [ ] persistencia de `style.json` por voz
- [ ] CRUD HTTP de estilos
- [ ] `style_id` estavel com rename do nome visivel
- [ ] referencia opcional normalizada por estilo
- [ ] limpeza da referencia de estilo
- [ ] leitura da midia original do estilo por HTTP
- [ ] persistencia de `instruction`
- [ ] persistencia de `parameters`

## Testes minimos

- `python -m pytest tests/test_voice_profiles.py -k create_style_persists_in_profile_and_disk -q`
- `python -m pytest tests/test_voice_profiles.py -k style_update_duplicate_reorder_and_delete -q`
- `python -m pytest tests/test_voice_profiles.py -k style_http_crud -q`
- `python -m pytest tests/test_voice_profiles.py -k "style_reference_persists_on_disk or style_reference_http_upload_and_fetch" -q`
- `python -m pytest tests/test_voice_profiles.py -k style_instruction_and_parameters_roundtrip -q`
- `python -m pytest tests/test_voice_profiles.py -k style_reference_http_delete_clears_media -q`
- `python -m pytest tests/test_voice_profiles.py -k style_original_audio_http_fetch -q`

## Dependencias

- `T2.1` verificado

## Criterio de parada

Parar quando a entidade `Style` estiver formalmente consolidada no tracker e no ledger, com suas pendencias restantes explicitadas, sem iniciar `T2.3` nem parser/orchestration.
```

## Issue proposta: `T2.3 — Implementar entidade Event`

```text
Titulo: AFK: Implementar T2.3 da entidade Event

## Parent

https://github.com/faleious-ai/EscribaLocal/issues/1

## Gate / Task

- Gate B
- T2.3 — Implementar entidade Event

## Objetivo

Implementar a entidade `Event` como audio curto persistido por voz, para respiracao, suspiro e risada, com comportamento deterministico e sem qualquer sintese substituta.

## Escopo

- persistencia de eventos por voz
- metadados minimos dos eventos
- gravar, importar, ouvir, substituir e excluir evento
- validar ausencia de evento como erro de roteiro quando a integracao for acionada

## Fora de escopo

- parser completo de eventos no roteiro
- AudioAssembler final
- timeline completa
- eventos gerados artificialmente
- UI completa alem do necessario para o slice

## Criterios de aceite

- [ ] eventos sao persistidos por voz
- [ ] e possivel gravar, importar, ouvir, substituir e excluir evento
- [ ] evento ausente pode gerar erro de validacao explicito no fluxo que o consumir
- [ ] nenhuma sintese substituta e gerada

## Testes minimos

- testes de persistencia e CRUD de eventos por voz
- teste negativo confirmando ausencia de fallback/sintese substituta

## Dependencias

- `T2.1`
- preferencialmente `T2.2` formalizado para manter coerencia do Gate B

## Criterio de parada

Parar quando a entidade `Event` existir como unidade persistente e testada, sem avancar para parser/AST ou montagem final.
```

## Issue proposta: `T3.1 — Captura real da primeira voz no wizard`

```text
Titulo: AFK: Implementar T3.1 de captura real da primeira voz no wizard

## Parent

https://github.com/faleious-ai/EscribaLocal/issues/1

## Gate / Task

- Gate B
- T3.1 — Incorporar captura no wizard

## Objetivo

Transformar a etapa informativa "Criar sua voz" em um fluxo real de captura/importacao dentro do wizard, para que o TTS nao pareca pronto sem identidade vocal valida.

## Escopo

- gravar ou importar sem sair do assistente
- consentimento explicito
- ouvir
- regravar
- aprovar
- nome sugerido "Minha voz"
- definir a voz como padrao automaticamente
- concluir setup sem marcar TTS como pronto quando a voz continuar pendente

## Fora de escopo

- estilos personalizados
- parser/orchestration
- Chatterbox multi-voz
- eventos
- timeline de renderizacao

## Criterios de aceite

- [ ] primeira voz pode ser criada no wizard
- [ ] nome sugerido "Minha voz"
- [ ] voz torna-se padrao automaticamente
- [ ] Chatterbox e VibeVoice que exigem referencia aparecem como pendentes sem voz
- [ ] concluir setup nao marca TTS como pronto quando pendente

## Testes minimos

- teste de wizard com voz criada/importada
- teste de wizard sem voz mantendo TTS pendente
- teste de consentimento obrigatorio

## Dependencias

- `T2.1`
- alinhamento com a biblioteca de vozes real

## Criterio de parada

Parar quando o wizard deixar de ser apenas informativo e passar a produzir uma primeira voz real ou manter o TTS explicitamente pendente, sem avancar para `T3.2` ou `T3.3`.
```

## Proposta de divisao para `T4.x / T5.x / T6.x / T7.x`

```text
1. AFK: Definir gramatica formal minima das tags (`T4.1`)
2. AFK: Implementar parser/AST minimo com erros estruturados (`T4.2`)
3. AFK: Validar roteiro contra biblioteca e capability matrix minima (`T4.3`)
4. AFK: Criar RenderPlan persistivel por segmento (`T5.1`)
5. AFK: Resolver falantes reais/virtuais no RenderPlan (`T5.2`)
6. AFK: Extrair normalizador modular PT-BR (`T6.1`)
7. AFK: Ampliar cobertura da normalizacao PT-BR (`T6.2`)
8. AFK: Criar AudioAssembler minimo baseado em timeline (`T7.1`)
```

Observacao: nesta rodada a divisao e apenas proposta de governanca. O detalhamento fino de cada uma deve acontecer depois da formalizacao de `T2.2`, `T2.3` e `T3.1`.
