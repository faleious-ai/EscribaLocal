# Roteamento de modelos, esforço e subagentes

## Quando carregar

Carregue este arquivo quando a tarefa envolver escolha de modelo, esforço,
orquestrador, subagentes, orçamento de tokens, recomendação da próxima execução
ou uso de `Ultra`.

## Princípio central

Use o menor modelo e o menor esforço que ainda permitam cumprir a tarefa com
segurança, evidência, validação e qualidade aceitável. Escale apenas quando a
ambiguidade, o risco ou a abrangência justificarem o custo adicional.

Não use como padrão o modelo mais forte, esforço alto, contexto amplo ou muitos
subagentes. Tarefas pequenas e diretamente testáveis devem permanecer baratas.

## Modelos disponíveis

| Modelo | Uso recomendado | Evitar quando |
| --- | --- | --- |
| `5.6 Sol` | Tarefas ambíguas, críticas, longas, multi-etapas ou com alto custo de erro: arquitetura, auditoria técnica, refatoração ampla, bug difícil, segurança, design, síntese final e reconciliação de subagentes. É o orquestrador preferencial quando o julgamento final precisa ser forte. | Listagem, extração simples, formatação, triagem mecânica, busca textual ou alteração pequena validável por teste direto. |
| `5.6 Terra` | Padrão econômico para trabalho substantivo: exploração de repositório, documentação, triagem técnica, revisão preliminar, implementação delimitada, investigação moderada, logs, preparação de insumos e orquestração comum de tarefas delimitadas. | Tarefa puramente mecânica que Luna resolve ou decisão crítica que exige Sol. |
| `5.6 Luna` | Trabalho rápido, barato, repetitivo, delimitado e de baixo risco: inventário, extração, classificação, normalização, busca, pré-sumarização, checagem mecânica, comparação simples e lote. | Arquitetura, refatoração profunda, segurança, ambiguidade relevante ou síntese final crítica. |
| `5.5` | Fallback forte ou intermediário quando Sol não é necessário, Terra parece insuficiente ou o fluxo já está calibrado em 5.5. Adequado para revisão técnica, implementação moderada e síntese média. | Substituir Sol em decisões críticas ou Luna/Terra em tarefas baratas. |
| `5.4` | Workflows legados, continuidade de trabalho iniciado nesse modelo, implementação comum, revisão moderada e fallback quando a família 5.6 não estiver adequada ou disponível. | Trabalho mecânico que 5.4 Mini resolve ou julgamento crítico que exige capacidade maior. |
| `5.4 Mini` | Tarefas mecânicas, responsivas e de baixo risco: listagem, busca, ajustes pequenos, formatação, extração simples e checagens locais. | Decisão técnica substantiva. |

Os nomes acima são os nomes normativos da interface. IDs internos de ferramentas
podem ser diferentes; consulte as capacidades expostas pelo ambiente e não
invente mapeamentos.

## Matriz de esforço

| Esforço | Quando usar |
| --- | --- |
| `Leve` | Tarefa mecânica, rápida, delimitada e com pouca inferência: listar, localizar, extrair, formatar, renomear com segurança, aplicar ajuste objetivo, checar branch, rodar comando simples, commit/push mecânico ou resumir saída curta. |
| `Médio` | Padrão para desenvolvimento e documentação normais: análise moderada, implementação delimitada, revisão documental, leitura de alguns arquivos, poucas hipóteses, atualização de plano e síntese operacional. |
| `Alto` | Múltiplas etapas, dependências cruzadas, risco de regressão ou validação cuidadosa: debugging complexo, revisão de PR, mudança transversal moderada, compatibilidade, testes e hipóteses concorrentes. |
| `Extra alto` | Arquitetura, migração, refatoração ampla, falha intermitente, segurança defensiva, decisão difícil, risco alto, resultados conflitantes ou síntese final crítica. |
| `Ultra` | Somente tarefas grandes, paralelizáveis e de alto valor que justificam raciocínio máximo e subagentes: auditoria ampla, revisão complexa de branch, investigação de vários subsistemas, segurança multivetor ou planejamento extenso. |

`Ultra` não serve para tarefas pequenas, sequenciais, mecânicas ou facilmente
validáveis. Ao usá-lo, registre por que a execução exigia subagentes e por que
`Extra alto` com subagentes explícitos não bastava.

## Procedimento de escolha

1. Classifique escopo, ambiguidade, risco, custo do erro e forma de validação.
2. Comece pelo menor modelo e esforço plausivelmente suficientes.
3. Rebaixe capacidade quando o problema ficar delimitado e testável.
4. Escale diante de ambiguidade real, alto risco, mudança transversal, falha não
   reproduzida, segurança, arquitetura ou síntese crítica.
5. Registre a justificativa ao usar modelo mais caro, esforço maior ou `Ultra`.

## Orquestrador e subagentes

O orquestrador é o agente principal que controla objetivo, escopo, restrições,
fila de trabalho, dependências, bloqueios, orçamento de tokens, decisões, riscos,
validação final e resposta consolidada. Ele deve ser o menor modelo suficiente
para conduzir a decisão principal.

Use `5.6 Sol` como orquestrador quando houver ambiguidade alta, decisão crítica,
arquitetura, segurança, refatoração ampla, reconciliação de subagentes
conflitantes ou síntese final de alto risco.

Use `5.6 Terra` como orquestrador padrão para trabalho substantivo, delimitado e
não crítico: exploração de repositório, revisão documental, implementação
moderada, triagem técnica, atualização de planos e condução de subagentes
simples.

Use `5.6 Luna` ou `5.4 Mini` como orquestrador apenas quando a rodada inteira for
mecânica, curta, de baixo risco e diretamente validável. Use `5.5` ou `5.4` como
fallback ou continuidade de workflow quando fizer sentido no ambiente local.

Subagentes devem ser proporcionais à subtarefa, não ao prestígio do
orquestrador. Use subagentes somente quando a tarefa puder ser dividida em
partes independentes e delimitadas. Cada delegação deve conter:

* objetivo fechado e critério de parada;
* arquivos-alvo e comandos permitidos;
* formato de retorno e limite de verbosidade;
* restrições de escrita, branch, publicação e escopo;
* evidências esperadas para validação.

Subagentes devem retornar achados destilados: caminhos, evidências, riscos,
conclusões e recomendações. Não devem despejar logs brutos, exploração
irrelevante ou raciocínio longo no contexto principal.

O orquestrador reconcilia conflitos, elimina duplicatas, verifica evidências e
decide o que entra no resultado. Não aceite conclusões de subagentes sem
validação proporcional ao risco.

Evite subagentes quando a tarefa for pequena, sequencial, depender de uma única
cadeia de raciocínio, exigir escrita concorrente nos mesmos arquivos ou tiver
custo de coordenação maior que o ganho.

## Orquestração contínua e subagentes

Subagentes não são apenas mecanismo de consulta; são mecanismo para avançar
frentes independentes sem contaminar o contexto principal. O orquestrador deve
usar subagentes para sustentar execução contínua quando houver trabalho
paralelizável e seguro.

Delegue para subagentes quando houver:

* investigação independente;
* leitura de módulos diferentes;
* inventário;
* testes e análise de logs;
* revisão paralela;
* preparação de insumos;
* auditoria de partes distintas.

Não use subagentes para escrita concorrente nos mesmos arquivos. Se um subagente
encontrar bloqueio, o orquestrador deve registrar o bloqueio, avaliar se ele
bloqueia outras frentes e redistribuir atenção para outra tarefa `Ready` ou
`Parallelizable`.

O orquestrador deve reconciliar resultados e decidir a sequência seguinte sem
pedir continuação quando a próxima ação estiver delimitada, autorizada e
desbloqueada.

## Roteamento de subagentes

| Modelo | Subtarefas recomendadas |
| --- | --- |
| `5.6 Luna` ou `5.4 Mini` | Inventário, extração, classificação, busca textual, normalização, pré-sumarização, checagens mecânicas e processamento em lote. Preferir esforço `Leve`. |
| `5.6 Terra` | Exploração de código, leitura documental, análise preliminar, revisão moderada, investigação de arquivos, logs e preparação de plano. Usar `Leve` ou `Médio` conforme risco. |
| `5.5` ou `5.4` | Fallback, continuidade de fluxo já calibrado nesses modelos ou indisponibilidade/inadequação da família 5.6. |
| `5.6 Sol` | Apenas subtarefas isoladas que também exijam julgamento forte: segurança, arquitetura, design, debugging difícil, validação crítica ou síntese de alto risco. Nos demais casos, mantenha Sol como orquestrador. |

## Controle rígido de tokens e contexto

* Não carregue o repositório inteiro por padrão.
* Comece por mapa de arquivos, buscas direcionadas e leitura sob demanda.
* Mantenha no contexto principal apenas requisitos, decisões, evidências
  relevantes, diffs propostos, riscos e próximos passos.
* Delegue exploração ruidosa, logs longos e buscas paralelizáveis quando houver
  ganho real.
* Prefira resumos estruturados a conteúdo bruto.
* Limite prompts de subagentes ao contexto mínimo necessário.
* Rebaixe modelo e esforço quando testes objetivos puderem validar a tarefa.
* Escale somente com justificativa baseada em risco, ambiguidade ou abrangência.

## Recomendação da próxima execução

Ao final, informe qualquer limitação de ambiente que impeça validar a escolha de
modelo, esforço ou subagente. Use sempre os nomes exatos da interface e recomende
a menor configuração de orquestração suficiente:

`Próxima execução: orquestrador <Modelo>, esforço <Leve|Médio|Alto|Extra alto|Ultra>; fila <ready|blocked|empty>: <resumo>; subagentes <nenhum|lista modelo/esforço/função>; decisão humana <não|sim — motivo>; suficiência: <motivo curto>; limite: <restrição de contexto/tokens/escopo>; continuidade: <persistida|requer handoff> — <onde retomar>; git: <limpo|pendente> — <último commit/ação>.`

Exemplos:

`Próxima execução: orquestrador 5.6 Terra, esforço Médio; fila ready: #18/T3.1; subagentes 2x 5.6 Luna Leve para inventário de UI e testes existentes; decisão humana não; suficiência: issue delimitada e desbloqueada; limite: não iniciar T4.x; continuidade: persistida em issue #18 e ledger TTS; git: limpo — último commit publicado em main.`

`Próxima execução: orquestrador 5.6 Sol, esforço Extra alto; fila ready: auditoria de arquitetura e testes; fila blocked-human: decisão Realtime #8; subagentes 3x 5.6 Terra Médio; decisão humana ainda não, pois há frentes independentes desbloqueadas; limite: não alterar Realtime nativo; continuidade: persistida em plano/ledger; git: limpo — checkpoint publicado.`

`Próxima execução: orquestrador 5.6 Terra, esforço Médio; fila blocked-human: todas as próximas ações dependem da decisão #8; subagentes nenhum; decisão humana sim — escolher estratégia nativa do Realtime 0.5B; suficiência: não há outra frente autorizada e desbloqueada; limite: não improvisar decisão; continuidade: persistida em issue #8; git: limpo — último commit publicado em main.`
