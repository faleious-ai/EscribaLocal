# Contrato canônico do RenderPlan — Gate C

Status: especificação normativa complementar para T5.1 e T5.2
Epic: #26
Issues: #24 e #25

Este documento aprofunda o Épico 5 do escopo consolidado sem substituir decisões gerais de produto. Em caso de conflito específico sobre RenderPlan, prevalece este contrato até que seu conteúdo seja incorporado ao documento consolidado.

## 1. Fronteira arquitetural

O fluxo canônico é:

```text
AST
→ resolução por segmento
→ normalização PT-BR
→ RenderPlan versionado
→ jobs de engine futuros
```

T5.1 e T5.2 terminam no manifesto. Não geram WAV, não chamam adapters, não montam áudio e não alteram UI.

## 2. T5.1 — RenderPlan persistível

### Objetivo

Converter o AST validado em jobs ordenados, serializáveis e recuperáveis, preservando estrutura editorial e identidade semântica.

### Contrato mínimo por job

- `job_id` ou `segment_id` estável;
- `section_id` e título/contexto de seção quando aplicável;
- `order`;
- `speaker_id` quando resolvido;
- `voice_id`;
- `style_id` canônico quando aplicável;
- referência relativa ou identificador de referência;
- parâmetros tipados;
- texto original;
- texto normalizado.

Campos de execução futura, como output, duração e erro, podem permanecer ausentes até os gates correspondentes.

### Critérios de aceite

- cada trecho possui identidade estável e semântica suficiente para regeneração localizada;
- seções e ordem são preservadas;
- texto original e normalizado permanecem separados;
- referências não usam caminhos absolutos;
- parâmetros preservam tipos suportados;
- manifesto possui versão explícita;
- manifesto é serializável e não gera áudio;
- cada critério possui teste ou evidência correspondente.

### Identidade determinística

O ID deve derivar de representação canônica dos campos semanticamente relevantes. Mudanças em seção, ordem, speaker, voz, estilo, referência, parâmetros ou texto devem alterar o ID. Entradas idênticas devem produzir o mesmo ID.

## 3. T5.2 — falantes reais e virtuais

### Objetivo

Usar a mesma mecânica de jobs para pessoas diferentes e para personagens/variantes que compartilham uma identidade vocal.

### Fluxo normativo de resolução

```text
nó AST
→ speaker lógico
→ voice_id mapeada
→ perfil da voz
→ style_id ou alias dentro dessa voz
→ referência de estilo ou referência neutra da mesma voz
→ parâmetros persistidos
→ sobrescritas inline
→ RenderJob
```

### Regras de speaker

- bloco sem `falante` usa a voz padrão fornecida explicitamente ao plano;
- bloco com `falante` exige mapeamento em `speaker_voices`;
- ausência de mapeamento é erro explícito;
- voz mapeada inexistente é erro explícito;
- speakers diferentes podem apontar para vozes diferentes;
- speakers diferentes podem apontar para a mesma voz;
- o namespace canônico é lógico (`ana`, `carlos`), não o namespace numérico legado (`1`, `2`, `speaker_1`).

### Regras de estilo

- estilo/alias é resolvido no perfil da voz daquele speaker;
- o manifesto registra `style_id` canônico, não apenas o texto digitado;
- estilo inexistente, inativo ou incompatível é erro explícito;
- o mesmo alias pode resolver de forma diferente em vozes diferentes, conforme seus perfis;
- conflitos de alias dentro de uma mesma voz não devem ser redefinidos incidentalmente nesta issue; precisam de contrato próprio se forem encontrados.

### Regras de referência

- referência própria do estilo com estado pronto tem precedência;
- ausência opcional de referência própria usa a referência neutra da mesma voz;
- mídia declarada pronta, mas ausente ou inconsistente, é erro;
- referências no manifesto são caminhos relativos controlados ou IDs, nunca caminhos absolutos.

### Regras de parâmetros

- parâmetros persistidos do estilo são a base;
- parâmetros inline sobrescrevem apenas o segmento;
- `falante` é estrutural e não aparece nos parâmetros enviados à engine;
- valores numéricos, booleanos e strings preservam seus tipos.

### Critérios de aceite

- cada job registra separadamente speaker, voz e estilo;
- duas vozes e dois estilos são representados corretamente no mesmo manifesto;
- uma voz alterna estilos entre trechos;
- ausência de speaker/voz/estilo falha sem fallback;
- alias é resolvido por voz;
- referência e parâmetros são resolvidos por segmento;
- ID muda quando qualquer entrada semântica relevante muda;
- construções idênticas permanecem determinísticas;
- manifesto serializa sem áudio.

## 4. Resolução compartilhada

Validação e construção do plano devem compartilhar a mesma regra de resolução por segmento ou consumir um objeto resolvido comum. Não é aceitável validar com um perfil e construir o plano por outra lógica.

Uma estrutura interna pode conter:

```text
speaker_id
voice_id
style_id
reference
parameters
section_id
original_text
normalized_text
```

O nome concreto da estrutura não é normativo; a equivalência semântica é.

## 5. Testes mínimos de gate

### T5.1

- preservação da seção em cada job;
- mudança de seção entre blocos;
- ordem entre seções;
- estabilidade e sensibilidade semântica dos IDs;
- serialização e versão do manifesto.

### T5.2

- dois speakers → duas vozes;
- mesma voz → dois estilos;
- speaker sem mapeamento;
- voz mapeada inexistente;
- alias resolvido por voz;
- merge de parâmetros e remoção de `falante`;
- referência de estilo e referência neutra;
- mudança de speaker/referência/parâmetro altera ID;
- caso simples sem speaker explícito preservado.

## 6. Fora de escopo

- conectar RenderPlan ao endpoint de geração;
- alterar engines, adapters ou worker Realtime;
- gerar WAVs;
- AudioAssembler;
- edição/reprodução por seção na interface;
- modo multi-speaker nativo do VibeVoice;
- política geral de colisão de aliases;
- validação final em hardware.

## 7. Gate de fechamento

Uma issue só fecha quando o comentário final contém:

- checklist de aceite concluído;
- mapeamento aceite → teste/evidência;
- commits publicados;
- comandos e resultados de verificação;
- limitações remanescentes;
- atualização do ledger e do runway quando a fila mudar.