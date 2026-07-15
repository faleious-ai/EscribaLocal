# TTS Current Runway

Última atualização: 2026-07-15
Gate ativo: C — Linguagem, validação e RenderPlan
Epic operacional: #26
Fonte canônica: `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`
Contrato específico: `docs/tts/RENDERPLAN_CONTRACT.md`

## Estado resumido

### Done

- #21 / T4.1 — gramática formal;
- #22 / T4.2 — parser e AST;
- #23 / T4.3 — validação contra biblioteca;
- #24 / T5.1 - RenderPlan persistivel concluido em `31bd3ca0`, com secoes e identidade semantica comprovadas;
- #25 / T5.2 - falantes reais e virtuais concluidos em `a8ffa8d7`, com resolucao por segmento e falhas sem fallback;
- #30 / T6.1 - normalizador PT-BR modular concluido em `d02fc83e`, com perfis explicitos e comportamento preservado.
- #31 / T6.2 - cobertura PT-BR ampliada, com regras deterministicas por classe linguistica e dicionario por chamada.
- #32 / T7.1 - AudioAssembler deterministico com WAV PCM mono a 24 kHz, timeline, pausas, eventos e fades de borda.
- #33 / T7.2 - regeneracao individual por cache de `job_id` e remontagem deterministica.
- #34 / T7.3 - transicao linear de 20 ms entre estilos adjacentes, sem crossfade em pausas/eventos.
- #35 / T8.1 - parametros reais do Chatterbox expostos, validados, aplicados por segmento e auditados.
- #36 / T8.2 - referencias Chatterbox por segmento com falha explicita e metadata auditavel.
- #37 / T8.3 - multi-voz Chatterbox orquestrado por segmento, com vozes, speakers e referencias auditaveis.
- #38 / T8.4 - cancelamento cooperativo entre segmentos e unload seguro apos job.

### Ready

- nenhuma; #39/T8.5 aguarda somente validação auditiva humana.

### In-progress

- #39 / T8.5 — cinco amostras reais geradas e round-trip auxiliar registrado em `docs/tts/T8.5_QA_REPORT.md`; escuta humana pendente.

### Blocked-technical

- nenhuma; Gate C pronto para fechamento.

### Blocked-human

- #8 — decisão nativa do Realtime 0.5B; independente do Gate C.
- #39 — escuta humana de naturalidade, prosódia, pronúncia e artefatos das amostras reais.

### Backlog / não executável agora

- #12 — validação final com áudio real e relatório; depende de gates posteriores.

## Próxima issue executável

Aguardar validação humana da issue #39/T8.5; não há outra fatia TTS segura antes dessa decisão.

## DAG imediato

```text
#21 -> #25 done -> Gate C done -> #30/T6.1 done -> #31/T6.2 done -> #32/T7.1 done -> #33/T7.2 done -> #34/T7.3 done -> #35/T8.1 done -> #36/T8.2 done -> #37/T8.3 done -> #38/T8.4 done -> #39/T8.5 pending-human
```

## Limites da próxima execução

- não iniciar T6.3 (preview/UI);
- não iniciar T7.2 na mesma issue de T7.1;
- não iniciar T8.6 enquanto #39/T8.5 não tiver aceite humano;
- não alterar engines, adapters, `main.py`, routers ou UI;
- não iniciar Realtime.

## Critério de parada da próxima execução

Parar até que #39/T8.5 receba validação auditiva humana e suas notas sejam persistidas; só então avaliar a próxima unidade.

## Regra de continuidade

Após cada checkpoint, atualizar primeiro a issue ativa e, se o estado da fila mudar, este arquivo e `EXECUTION_STATUS.md`. O chat não é fonte suficiente de memória.

## Configuração GitHub ainda pendente

O conector desta rodada não expôs criação de GitHub Project, milestone, sub-issues ou dependências nativas. A configuração exata está persistida em `docs/tts/GITHUB_PROJECT_SETUP.md`. Até execução por UI/CLI, #26 e o DAG textual são a projeção operacional do Gate C.
