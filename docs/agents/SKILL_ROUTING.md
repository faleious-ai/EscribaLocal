# Roteamento de skills

## Quando carregar

Carregue este arquivo antes de planejar ou executar tarefa não trivial,
especialmente quando houver mudança de produto, código, arquitetura,
documentação, issue, bug, teste, QA, revisão ou continuidade.

## Princípio

Antes de planejar, editar arquivos ou executar mudanças, classifique a tarefa e
use explicitamente a skill instalada mais apropriada. Informe no início da
resposta:

`Roteamento: $nome-da-skill — motivo`

Quando a tarefa for realmente trivial:

`Roteamento: execução direta — tarefa trivial e completamente especificada`

Considere trivial apenas uma alteração localizada, mecânica, reversível e sem
decisões de produto, arquitetura, domínio, segurança, integração ou experiência
do usuário.

Use apenas skills realmente instaladas. Nunca afirme ter usado uma skill que não
foi carregada.

## Regras de roteamento

* Use `$setup-matt-pocock-skills` quando a configuração das skills, dos
  documentos de domínio, dos ADRs, das labels ou do issue tracker estiver ausente
  ou inconsistente.

* Use `$grill-with-docs` antes de implementar uma nova funcionalidade,
  integração ou mudança relevante que ainda possua ambiguidades, decisões abertas
  ou múltiplas soluções possíveis. Explore primeiro o código e os documentos.
  Faça uma pergunta por vez e apresente uma recomendação.

* Use `$to-prd` quando os requisitos já estiverem suficientemente resolvidos e
  precisarem virar uma especificação implementável. Não invente requisitos nem
  comece uma nova entrevista extensa.

* Use `$to-issues` quando existir um PRD ou uma especificação aprovada que
  precise ser dividida em unidades executáveis. Prefira fatias verticais,
  pequenas, demonstráveis e testáveis.

* Use `$tdd` para implementar comportamento bem definido. Trabalhe em ciclos
  pequenos: teste falhando, implementação mínima, teste passando e refatoração.

* Use `$diagnose` antes de corrigir bugs cuja causa raiz ainda seja desconhecida.
  Primeiro reproduza, reúna evidências, teste hipóteses e identifique a causa;
  depois implemente a correção com `$tdd` quando aplicável.

* Use `$improve-codebase-architecture` para auditoria arquitetural, acoplamento
  excessivo, modularização ou refatoração estrutural. Não transforme
  automaticamente uma auditoria em reescrita geral.

* Use `$prototype` quando uma dúvida técnica puder ser resolvida com um
  experimento pequeno, isolado e descartável.

* Use `$review` ao concluir mudanças relevantes ou quando o usuário solicitar
  revisão do código ou do diff.

* Use `$qa` quando os critérios de aceite exigirem validação integrada, de
  interface, API ou fluxo ponta a ponta.

* Use `$handoff` somente quando o trabalho precisar continuar em outra sessão e a
  continuidade necessária ainda não estiver suficientemente persistida no
  repositório. Antes de usar `$handoff`, prefira atualizar issue, ledger, plano
  ou documento de status.

## Fluxos padrão

Nova funcionalidade:

`$grill-with-docs → $to-prd → $to-issues → $tdd → $review → $qa quando aplicável`

Bug sem causa conhecida:

`$diagnose → $tdd → $review`

Mudança arquitetural:

`$improve-codebase-architecture → $to-prd quando necessário → $to-issues → $tdd → $review`

Não execute automaticamente todo o fluxo pulando artefatos obrigatórios,
critérios de aceite ou validações proporcionais. Porém, quando a saída de uma
etapa existir, a próxima etapa estiver delimitada, autorizada e desbloqueada, o
orquestrador deve continuar sem pedir nova autorização. A parada deve ocorrer por
bloqueio real, não por término de microetapa.

Consulte `docs/agents/AUTONOMOUS_RUNWAY.md` quando houver fila de tarefas,
backlog, múltiplas frentes ou bloqueios parciais.
