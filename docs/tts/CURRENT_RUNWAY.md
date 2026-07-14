# TTS Current Runway

Última atualização: 2026-07-10
Gate ativo: C — Linguagem, validação e RenderPlan
Epic operacional: #26
Fonte canônica: `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`
Contrato específico: `docs/tts/RENDERPLAN_CONTRACT.md`

## Estado resumido

### Done

- #21 / T4.1 — gramática formal;
- #22 / T4.2 — parser e AST;
- #23 / T4.3 — validação contra biblioteca;
- #24 / T5.1 ? RenderPlan persist?vel conclu?do em `31bd3ca0`, com se??es e identidade sem?ntica comprovadas.

### Ready

- #25 / T5.2 ? depend?ncia de T5.1 resolvida; pronta para resolu??o de falantes reais e virtuais por segmento.

### Blocked-technical

- nenhuma no Gate C imediato.

### Blocked-human

- #8 — decisão nativa do Realtime 0.5B; independente do Gate C.

### Backlog / não executável agora

- #12 — validação final com áudio real e relatório; depende de gates posteriores.

## Próxima issue executável

#25 ? resolver, por segmento, speaker l?gico, voz, estilo can?nico, refer?ncia e par?metros, sem gerar ?udio.

## DAG imediato

```text
#21 done ? #22 done ? #23 done ? #24 done ? #25 ready
```

## Limites da próxima execução

- não implementar T5.2;
- não alterar engines, adapters, `main.py`, routers ou UI;
- não gerar nem montar áudio;
- não iniciar Realtime;
- não ampliar T5.1 para AudioAssembler ou timeline final.

## Critério de parada da próxima execução

Parar quando #25 cumprir integralmente o contrato revisado, com testes focais e su?te relevante registrados, ledger atualizado e issue fechada; ent?o reavaliar a fila do Gate C.

## Regra de continuidade

Após cada checkpoint, atualizar primeiro a issue ativa e, se o estado da fila mudar, este arquivo e `EXECUTION_STATUS.md`. O chat não é fonte suficiente de memória.

## Configuração GitHub ainda pendente

O conector desta rodada não expôs criação de GitHub Project, milestone, sub-issues ou dependências nativas. A configuração exata está persistida em `docs/tts/GITHUB_PROJECT_SETUP.md`. Até execução por UI/CLI, #26 e o DAG textual são a projeção operacional do Gate C.
