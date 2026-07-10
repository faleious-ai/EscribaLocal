# TTS Issue Execution Plan

Data: 2026-07-10
Gate ativo: C — Linguagem, validação e RenderPlan
Epic operacional: #26
Cursor: `docs/tts/CURRENT_RUNWAY.md`
Ledger: `docs/tts/EXECUTION_STATUS.md`
Contrato: `docs/tts/RENDERPLAN_CONTRACT.md`

## Objetivo

Manter uma fila executável, pequena e auditável para concluir Gate C sem misturar
RenderPlan com engines, geração, UI ou montagem de áudio.

## Precedência

1. decisão explícita mais recente do usuário;
2. especificação consolidada;
3. `RENDERPLAN_CONTRACT.md` para T5.1/T5.2;
4. issue ativa delimitada;
5. ledger e runway;
6. ADRs compatíveis;
7. documentos operacionais;
8. materiais históricos.

## DAG do Gate C

```text
#21 / T4.1 — done
  ↓
#22 / T4.2 — done
  ↓
#23 / T4.3 — done
  ↓
#24 / T5.1 — ready após reabertura
  ↓
#25 / T5.2 — blocked-technical
```

## Matriz tarefa → issue

| Task | Issue | Estado | Evidência | Próxima ação |
| --- | --- | --- | --- | --- |
| T4.1 | #21 | Done | gramática e revisão documental | preservar contrato |
| T4.2 | #22 | Done | testes focais e suíte registrados | preservar AST |
| T4.3 | #23 | Done | validação pura e suíte registradas | preservar fronteira |
| T5.1 | #24 | Partial / Ready | manifesto básico e `260 passed`; aceite de seção ausente | reabrir, corrigir e provar aceite |
| T5.2 | #25 | Blocked-technical | contrato aprofundado, sem implementação | aguardar #24 |

## Critério de entrada de uma issue

Uma issue só entra em `ready-for-agent` quando:

- objetivo, escopo, fora de escopo, aceite e parada estão claros;
- dependências estão concluídas;
- riscos e testes mínimos estão definidos;
- não há decisão humana pendente;
- o contrato canônico aplicável foi carregado.

## Critério de fechamento

Seguir `docs/agents/AUTONOMY_AND_GIT.md`. Exigir:

- checklist integral;
- mapa aceite → evidência;
- testes focais e suíte relevante;
- commits publicados;
- limitações registradas;
- ledger/runway sincronizados;
- dependentes retriados.

## Próxima execução única

### #24 — concluir T5.1

Escopo:

- preservar seção em cada job;
- preservar ordem entre e dentro de seções;
- fortalecer identidade determinística com os campos semanticamente relevantes;
- manter manifesto serializável/versionado;
- adicionar testes diretamente ligados ao aceite.

Fora de escopo:

- falantes reais/virtuais de T5.2;
- resolução multi-voz;
- engines/adapters;
- endpoints e UI;
- geração ou montagem de áudio;
- Realtime.

Parada:

- #24 fechada com aceite → evidência;
- ledger/runway atualizados;
- #25 retriada.

## Fila posterior

Depois de #24:

1. revisar #25 contra `RENDERPLAN_CONTRACT.md`;
2. aplicar `ready-for-agent` somente se a predecessora estiver fechada;
3. implementar resolução por segmento;
4. parar antes de integração com engines.

## Bloqueios fora da cadeia

- #8: `Blocked-human` para Realtime nativo; não bloqueia Gate C;
- #12: validação final; não é tarefa atual.

## GitHub Project, milestone e dependências nativas

Configuração desejada:

- Project: `EscribaLocal — TTS Governed Delivery`;
- milestone: `TTS Gate C — Linguagem, validação e RenderPlan`;
- #21–#25 como filhos de #26;
- dependências nativas na ordem do DAG.

O conector usado nesta rodada não expõe criação de Project, milestone, sub-issues
ou dependências nativas. Até configuração por UI/CLI, #26, este plano e os corpos
das issues são a representação operacional; não declarar esses recursos como
criados.

## Regra de manutenção

Este arquivo contém apenas o gate ativo e a fila imediata. Histórico detalhado
fica no ledger/Git. Quando o gate mudar, substitua a seção operacional em vez de
acumular drafts, comentários propostos e planos obsoletos.