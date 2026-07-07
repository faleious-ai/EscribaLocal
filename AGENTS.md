# AGENTS.md

Sempre se comunique com o usuário em português do Brasil (pt-BR), inclusive em perguntas, explicações, relatórios e conclusões. Preserve em inglês apenas código, comandos, caminhos, identificadores e termos técnicos cuja tradução possa causar ambiguidade.

## Configuração do projeto

### Regime de trabalho Git

Decisão operacional vigente: todo trabalho deve acontecer diretamente em
`main`. Não crie branches de trabalho, branches `codex/*` ou branches paralelas
sem uma instrução explícita posterior do usuário revogando esta decisão.

Se encontrar trabalho em outra branch, consolide-o em `main` antes de
continuar, preservando alterações locais e sem descartar commits. Depois da
consolidação local, remova a branch paralela local quando ela não for mais
necessária.

Mesmo trabalhando em `main`, continue respeitando as proteções deste arquivo:
não faça commit, push, merge remoto, rebase, release, deploy ou alterações
remotas sem autorização explícita.

### Skills e ambiente do agente

Este repositório versiona:

* instruções de operação em `AGENTS.md`;
* contexto e convenções em `docs/agents/`;
* documentação de domínio em `docs/`, `CONTEXT.md` e ADRs.

As skills em si normalmente **não** ficam versionadas dentro deste repositório. Elas costumam estar instaladas no ambiente do agente (por exemplo, em diretórios do Codex/Claude/Gemini CLI) e são apenas **roteadas** por estas instruções.

Leia quando aplicável:

* `docs/agents/skills-runtime.md`

### Issues e PRDs

Issues e PRDs são gerenciados no GitHub Issues de `faleious-ai/EscribaLocal`.

Leia quando aplicável:

* `docs/agents/issue-tracker.md`

### Triagem

Este repositório utiliza os rótulos:

* `needs-triage`
* `needs-info`
* `ready-for-agent`
* `ready-for-human`
* `wontfix`

Detalhes:

* `docs/agents/triage-labels.md`

### Contexto de domínio

Este é um repositório de contexto único.

Antes de planejar ou modificar comportamento não trivial, leia:

* `CONTEXT.md`;
* ADRs aplicáveis em `docs/adr/`;
* documentação relacionada em `docs/`;
* instruções aplicáveis em `docs/agents/`.

Não pergunte ao usuário algo que possa ser descoberto examinando o repositório.

## Roteamento obrigatório de skills

Antes de planejar, editar arquivos ou executar mudanças, classifique a tarefa e use explicitamente a skill instalada mais apropriada.

Informe no início da resposta:

`Roteamento: $nome-da-skill — motivo`

Quando a tarefa for realmente trivial:

`Roteamento: execução direta — tarefa trivial e completamente especificada`

Considere trivial apenas uma alteração localizada, mecânica, reversível e sem decisões de produto, arquitetura, domínio, segurança, integração ou experiência do usuário.

### Regras de roteamento

* Use `$setup-matt-pocock-skills` quando a configuração das skills, dos documentos de domínio, dos ADRs, das labels ou do issue tracker estiver ausente ou inconsistente.

* Use `$grill-with-docs` antes de implementar uma nova funcionalidade, integração ou mudança relevante que ainda possua ambiguidades, decisões abertas ou múltiplas soluções possíveis. Explore primeiro o código e os documentos. Faça uma pergunta por vez e apresente uma recomendação.

* Use `$to-prd` quando os requisitos já estiverem suficientemente resolvidos e precisarem virar uma especificação implementável. Não invente requisitos nem comece uma nova entrevista extensa.

* Use `$to-issues` quando existir um PRD ou uma especificação aprovada que precise ser dividida em unidades executáveis. Prefira fatias verticais, pequenas, demonstráveis e testáveis.

* Use `$tdd` para implementar comportamento bem definido. Trabalhe em ciclos pequenos: teste falhando, implementação mínima, teste passando e refatoração.

* Use `$diagnose` antes de corrigir bugs cuja causa raiz ainda seja desconhecida. Primeiro reproduza, reúna evidências, teste hipóteses e identifique a causa; depois implemente a correção com `$tdd` quando aplicável.

* Use `$improve-codebase-architecture` para auditoria arquitetural, acoplamento excessivo, modularização ou refatoração estrutural. Não transforme automaticamente uma auditoria em reescrita geral.

* Use `$prototype` quando uma dúvida técnica puder ser resolvida com um experimento pequeno, isolado e descartável.

* Use `$review` ao concluir mudanças relevantes ou quando o usuário solicitar revisão do código ou do diff.

* Use `$qa` quando os critérios de aceite exigirem validação integrada, de interface, API ou fluxo ponta a ponta.

* Use `$handoff` quando o trabalho precisar continuar em outra sessão ou quando houver risco de perda de contexto.

Use apenas skills realmente instaladas. Nunca afirme ter usado uma skill que não foi carregada.

## Fluxos padrão

Nova funcionalidade:

`$grill-with-docs → $to-prd → $to-issues → $tdd → $review → $qa quando aplicável`

Bug sem causa conhecida:

`$diagnose → $tdd → $review`

Mudança arquitetural:

`$improve-codebase-architecture → $to-prd quando necessário → $to-issues → $tdd → $review`

Não execute automaticamente todo o fluxo de uma vez. Use somente a etapa apropriada ao estado atual e avance quando a saída necessária da etapa anterior existir.

## Recomendação para a próxima rodada

Ao concluir uma etapa ou responder sobre próximos passos, inclua sempre uma linha curta recomendando o modelo e o nível de esforço para a próxima rodada, identificando qual plataforma está em uso no momento e fornecendo a recomendação pertinente:

* **Na plataforma Codex**:
  * `GPT-5.5` — para tarefas complexas, arquitetura, integrações amplas e debugging difícil.
  * `GPT-5.4` — para implementação cotidiana com bom equilíbrio entre qualidade e custo.
  * `GPT-5.4-Mini` — para perguntas simples, revisão rápida, documentação e edições mecânicas.
  * `Codex Auto Review` — para rodadas focadas apenas em revisão automática de código/diff.
* **Na plataforma Antigravity**:
  * `Claude Sonnet 4.6 (Thinking)` ou `Gemini 3.1 Pro (High)` — para tarefas complexas, arquitetura, integrações e debugging difícil.
  * `Gemini 3.1 Pro (Low)` ou `Gemini 3.5 Flash (High)` — para implementação cotidiana e tarefas gerais.
  * `Gemini 3.5 Flash (Low)` ou `Gemini 3.5 Flash (Medium)` — para perguntas simples, revisões, edições mecânicas ou documentação.

Formato preferido:

`Próxima rodada recomendada: modelo <Modelo Recomendado>, esforço <baixo|médio|alto|muito alto> — <motivo curto>.`

Use esforço baixo para perguntas simples ou edições mecânicas, médio para implementações localizadas com testes, alto para arquitetura/integrações/bugs difíceis e muito alto apenas quando a próxima rodada exigir exploração profunda, alto risco ou múltiplas decisões encadeadas.

## Proteções

* Inspecione `git status` antes de editar.
* Não descarte nem sobrescreva alterações existentes do usuário.
* Não amplie o escopo sem autorização.
* Não reescreva a aplicação quando uma alteração incremental for viável.
* Não exponha nem modifique segredos ou credenciais reais.
* Não faça commit, push, merge, rebase, release, deploy ou alterações remotas sem autorização explícita.
* Execute testes e verificações relevantes antes de declarar o trabalho concluído.
* Revise o diff final e informe verificações que não puderam ser executadas.
