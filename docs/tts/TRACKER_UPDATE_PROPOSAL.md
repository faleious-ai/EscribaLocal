# Tracker Update Proposal - TTS

Data: 2026-06-16

Este arquivo e uma proposta de texto para o tracker. Nao foi publicado
comentario, nao foi criada issue e nenhuma issue existente foi alterada.

## Comentario recomendado para a issue-mae historica

```markdown
O escopo historico de TTS foi substituido como fonte de verdade operacional por:

- `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`
- `docs/tts/EXECUTION_STATUS.md`
- `docs/tts/gate-a-report.md`

O Gate A esta focado exclusivamente em restaurar confianca: remover caminhos funcionais de SAPI5, senoide, presets Windows, smoke sintetico, fallback de engine/voz e Large com referencia artificial. A PRD/issue historica deve permanecer como registro, mas nao limita o escopo atual quando divergir desses documentos.

Branch de trabalho: `codex/tts-gate-a`
PR de revisao: #15 draft

Proximo gate permitido apos revisao externa do Gate A: Gate B, iniciando por T2.1 (versionamento/migracao do `profile.json` e primeira voz real). Parser, RenderPlan, estilos, multi-voz avancado e Realtime nativo nao devem ser iniciados antes do Gate B/C/F correspondentes.
```

## Corpo recomendado para nova issue-mae do escopo atual

```markdown
## Objetivo

Executar o plano atual do subsistema TTS do EscribaLocal conforme `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`, usando `docs/tts/EXECUTION_STATUS.md` como ledger de progresso e relatorios por gate como evidencia auditavel.

## Fonte de verdade

1. Decisoes explicitas mais recentes do usuario.
2. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`.
3. `docs/tts/EXECUTION_STATUS.md`.
4. Relatorio do gate atual.
5. ADRs aceitos que nao contradigam o escopo.

## Sequencia de gates

- Gate A: remover SAPI5, senoide, voz Windows/presets e smoke sintetico; bloquear fallback e Large artificial.
- Gate B: consolidar dados de voz real, `profile.json`, migracoes idempotentes e primeira voz real.
- Gate C: parser/RenderPlan/AudioAssembler por segmentos.
- Gate D: engines Chatterbox/VibeVoice no RenderPlan sem troca silenciosa.
- Gate E: UX operacional, estilos, timeline, jobs e metadados.
- Gate F: Realtime nativo isolado, QA real e fechamento.

## Estado atual

Gate A em revisao na branch `codex/tts-gate-a`, PR #15 draft.

## Criterios de aceite globais

- Nenhum caminho funcional de SAPI5, voz Windows, senoide ou smoke sintetico em producao.
- Nenhum fallback de engine, voz ou identidade.
- Vozes reais preservadas; selecoes antigas migradas de forma idempotente ou limpas.
- Engine solicitada deve ser a engine executada e declarar `engine_key` explicita.
- Large permanece bloqueado sem referencias reais por speaker.
- Realtime so fica disponivel apos worker isolado retornar PCM/WAV nativo real validado.
- Relatorios e ledger atualizados a cada gate.

## Proximo passo

Concluir revisao externa do Gate A. Se aprovado, abrir/derivar issues pequenas para Gate B comecando por T2.1.
```
