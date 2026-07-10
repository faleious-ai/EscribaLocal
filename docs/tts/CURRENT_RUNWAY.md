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
- #23 / T4.3 — validação contra biblioteca.

### Ready

- #24 / T5.1 — reabrir e concluir o aceite incompleto do RenderPlan persistível.

### Blocked-technical

- #25 / T5.2 — depende da conclusão real de #24.

### Blocked-human

- #8 — decisão nativa do Realtime 0.5B; independente do Gate C.

### Backlog / não executável agora

- #12 — validação final com áudio real e relatório; depende de gates posteriores.

## Próxima issue executável

#24 — corrigir exclusivamente o contrato de T5.1: preservar seções no manifesto, fortalecer identidade determinística e produzir evidência explícita para cada critério de aceite.

## DAG imediato

```text
#21 done → #22 done → #23 done → #24 ready → #25 blocked
```

## Limites da próxima execução

- não implementar T5.2;
- não alterar engines, adapters, `main.py`, routers ou UI;
- não gerar nem montar áudio;
- não iniciar Realtime;
- não ampliar T5.1 para AudioAssembler ou timeline final.

## Critério de parada da próxima execução

Parar quando #24 cumprir integralmente o contrato revisado, com testes focais e suíte relevante registrados, ledger atualizado, issue fechada e #25 retriada.

## Regra de continuidade

Após cada checkpoint, atualizar primeiro a issue ativa e, se o estado da fila mudar, este arquivo e `EXECUTION_STATUS.md`. O chat não é fonte suficiente de memória.

## Limitação da configuração GitHub nesta rodada

O conector disponível permite criar e atualizar arquivos/issues, mas não expõe criação de GitHub Project, milestone, sub-issues ou dependências nativas. Enquanto esses recursos não forem configurados na UI/CLI, #26 e o DAG textual são a projeção operacional do Gate C.