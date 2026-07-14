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
- #24 / T5.1 - RenderPlan persistivel concluido em `31bd3ca0`, com secoes e identidade semantica comprovadas;
- #25 / T5.2 - falantes reais e virtuais concluidos em `a8ffa8d7`, com resolucao por segmento e falhas sem fallback;
- #30 / T6.1 - normalizador PT-BR modular concluido em `d02fc83e`, com perfis explicitos e comportamento preservado.

### Ready


### Blocked-technical

- nenhuma; Gate C pronto para fechamento.

### Blocked-human

- #8 — decisão nativa do Realtime 0.5B; independente do Gate C.

### Backlog / não executável agora

- #12 — validação final com áudio real e relatório; depende de gates posteriores.

## Próxima issue executável

Formalizar T6.2 - ampliar cobertura de normalizacao PT-BR - como proxima issue executavel.

## DAG imediato

```text
#21 -> #25 done -> Gate C done -> #30/T6.1 done -> T6.2 next
```

## Limites da próxima execução

- não implementar T5.2;
- não alterar engines, adapters, `main.py`, routers ou UI;
- não gerar nem montar áudio;
- não iniciar Realtime;
- não ampliar T5.1 para AudioAssembler ou timeline final.

## Critério de parada da próxima execução

Parar a proxima unidade quando T6.2 estiver delimitada, implementada, testada e persistida; nao iniciar T6.3 na mesma issue.

## Regra de continuidade

Após cada checkpoint, atualizar primeiro a issue ativa e, se o estado da fila mudar, este arquivo e `EXECUTION_STATUS.md`. O chat não é fonte suficiente de memória.

## Configuração GitHub ainda pendente

O conector desta rodada não expôs criação de GitHub Project, milestone, sub-issues ou dependências nativas. A configuração exata está persistida em `docs/tts/GITHUB_PROJECT_SETUP.md`. Até execução por UI/CLI, #26 e o DAG textual são a projeção operacional do Gate C.
