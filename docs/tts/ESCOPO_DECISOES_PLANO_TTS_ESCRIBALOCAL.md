# EscribaLocal TTS — Escopo decisório, arquitetura-alvo e plano consolidado de tarefas

**Status:** especificação de produto e arquitetura para implementação incremental
**Data-base da auditoria:** 16 de junho de 2026
**Repositório:** `faleious-ai/EscribaLocal`
**Snapshot auditado:** commit `b342721c34d883bf9769a3f6c066188b4e29f2a4` — `fix(chatterbox): harden local runtime and long-form generation`
**Documento anterior relacionado:** `PROMPT_MESTRE_TTS_ESCRIBALOCAL.md`
**Objetivo deste documento:** fornecer contexto suficiente para que um agente tome decisões coerentes em cada tarefa sem reinterpretar requisitos já resolvidos.

---

# Como usar este documento

Este documento possui duas partes complementares:

1. **Parte I — Escopo e decisões:** define o que o produto deve ser, como deve funcionar, por que as decisões foram tomadas e quais alternativas foram rejeitadas.
2. **Parte II — Plano consolidado de tarefas:** converte as decisões em uma sequência executável, com dependências, critérios de aceite e testes.

Quando existir conflito entre documentos, use esta ordem:

1. decisão explícita mais recente do usuário;
2. este documento;
3. ADRs aceitos que não contradigam este documento;
4. `AGENTS.md` e documentação operacional;
5. issues e PRDs antigas, apenas como registro histórico;
6. comportamento legado do código.

A issue histórica “PRD: TTS local verificável com VibeVoice e Chatterbox PT-BR” continua útil para compreender a origem do trabalho, mas **não contém os refinamentos posteriores sobre estilos personalizados, tags diretas, falantes virtuais, subtítulos e montagem por segmentos**. Ela não deve limitar o escopo definido aqui.

---

# PARTE I — ESCOPO, CONTEXTO E DECISÕES

# 1. Visão do produto

O EscribaLocal deve possuir um subsistema de TTS:

- totalmente local;
- verificável;
- centrado em português brasileiro;
- capaz de usar identidades vocais reais criadas pelo usuário;
- capaz de oferecer mais de uma engine sem misturá-las;
- capaz de organizar fala expressiva e múltiplos falantes por uma camada própria de orquestração;
- transparente sobre o que cada modelo realmente suporta;
- estável no hardware-alvo atual: RTX 3050 de 6 GB, 32 GB de RAM e Windows 11.

O produto não deve tentar esconder limitações dos modelos. Quando uma função não for nativa, ela deve ser apresentada como **orquestração virtual** ou **condicionamento por referência**, e não como capacidade nativa da engine.

---

# 2. Vocabulário obrigatório

Os termos abaixo não são intercambiáveis.

## 2.1. Engine

Implementação responsável por converter texto em áudio.

Exemplos:

- VibeVoice 1.5B;
- VibeVoice Realtime 0.5B;
- VibeVoice Large;
- Chatterbox PT-BR.

## 2.2. Voz ou identidade vocal

Representa uma pessoa ou personagem reconhecível. É criada a partir de uma gravação ou arquivo autorizado.

Uma voz contém:

- referência neutra;
- gravação original;
- metadados e consentimento;
- referências opcionais de estilo;
- eventos vocais opcionais;
- artefatos derivados separados por engine.

## 2.3. Falante

Papel dentro de um roteiro ou diálogo. Um falante aponta para uma identidade vocal.

Exemplo:

```text
Falante: ana
Voz associada: voice_id da Ana
```

## 2.4. Estilo

Forma como uma identidade vocal deve falar em determinado trecho.

Exemplos:

- acolhedor;
- sério;
- didático;
- entusiasmado;
- “professor paciente”, criado pelo usuário.

Um estilo pode combinar:

- referência de áudio opcional;
- parâmetros universais;
- parâmetros específicos da engine;
- instrução de gravação;
- texto de captura;
- aliases de tag.

Um estilo **não é uma voz diferente**.

## 2.5. Preset de parâmetros

Conjunto editável de valores. Pode ajudar a inicializar um estilo, mas não substitui uma referência vocal e não deve ser apresentado como identidade.

## 2.6. Evento vocal

Áudio curto inserido de forma determinística na linha do tempo.

Exemplos:

- respiração curta;
- respiração profunda;
- suspiro;
- risada leve.

## 2.7. Segmento

Unidade mínima de renderização. Possui texto falado, falante, voz, estilo, parâmetros, engine e posição na linha do tempo.

## 2.8. Orquestração virtual

Camada criada pelo EscribaLocal para simular ou organizar estilos, prosódia, emoções, pausas e múltiplos falantes por meio de:

- interpretação de tags;
- divisão do texto em segmentos;
- seleção de voz e referência;
- aplicação de parâmetros;
- geração independente de cada trecho;
- montagem posterior dos áudios.

As engines não precisam compreender as tags. As tags nunca são enviadas literalmente ao TTS.

---

# 3. Princípios não negociáveis

## 3.1. Totalmente local

Todo processamento de voz, condicionamento, normalização, renderização e montagem ocorre localmente.

É permitido baixar pesos e dependências oficiais. Depois de instalados, os modelos devem funcionar sem API externa.

## 3.2. Uma solicitação, uma engine

A engine escolhida deve:

- produzir o áudio; ou
- falhar explicitamente.

Nunca trocar para outra engine.

## 3.3. Nenhum fallback de voz ou áudio

São proibidos em produção:

- SAPI5;
- `pyttsx3`;
- `System.Speech`;
- vozes do Windows;
- senoide;
- tom de diagnóstico apresentado como síntese;
- silêncio apresentado como áudio válido;
- voz embutida usada quando a voz escolhida falha;
- engine substituta.

## 3.4. Sem identidade vocal de fábrica

O aplicativo não distribui uma voz humana padrão. A primeira voz real é criada ou importada pelo usuário.

## 3.5. Transparência de capacidade

Cada função deve ser classificada como:

- nativa;
- orquestrada;
- experimental;
- parcialmente compatível;
- incompatível;
- não validada.

## 3.6. Falha explícita

O sistema não deve retornar sucesso quando:

- o modelo não carregou;
- a voz não existe;
- o estilo solicitado não pode ser aplicado;
- um evento não está disponível;
- um segmento não foi gerado;
- uma montagem ficou incompleta.

---

# 4. Decisões aceitas e alternativas rejeitadas

## D01 — Chatterbox PT-BR entra como nova engine, não como substituto

### Decisão aceita

Adicionar `ResembleAI/Chatterbox-Multilingual-pt-br` como engine selecionável e independente.

### Como

- chave própria no catálogo;
- adaptador próprio;
- cache próprio;
- parâmetros próprios;
- metadados próprios;
- artefatos derivados próprios;
- integração com a biblioteca de vozes compartilhando apenas o áudio de referência.

### Por quê

O Chatterbox dedicado a PT-BR é mais alinhado ao objetivo de voz brasileira natural e clonada. Porém, o VibeVoice continua útil para comparação, long-form e recursos específicos.

### Rejeitado

**Substituir ou remover VibeVoice.**
Rejeitado porque o usuário solicitou explicitamente coexistência e porque as engines têm características diferentes.

**Usar o checkpoint multilíngue genérico como substituição silenciosa.**
Rejeitado porque o foco é PT-BR e a variante dedicada deve ser verificável.

---

## D02 — SAPI5, senoide e vozes Windows devem ser removidos do código de produção

### Decisão aceita

Eliminar completamente caminhos funcionais de SAPI5, presets Windows e geração senoidal.

### Como

- remover funções, imports, presets e testes que legitimem esses caminhos;
- migrar configurações antigas;
- impedir que o Large ou qualquer adapter crie referência artificial;
- manter diagnóstico sem áudio, por status e logs estruturados.

### Por quê

A existência desses caminhos permite falsos positivos: o usuário acredita estar ouvindo uma engine neural ou uma voz clonada quando o áudio veio de outra fonte.

### Rejeitado

**Manter SAPI5 “honestamente rotulado”.**
Rejeitado porque o produto é de clonagem e TTS local neural; manter vozes Windows confunde identidade vocal, testes e UX.

**Manter senoide apenas como smoke test dentro do worker.**
Rejeitado para o produto. Um teste técnico pode validar transporte de bytes sem áudio, por mocks ou fixtures, sem manter um gerador sonoro alcançável pelo runtime.

---

## D03 — A primeira voz deve ser criada na instalação ou primeira execução

### Decisão aceita

O assistente deve incorporar a captura ou importação da primeira voz.

### Como

- etapa “Criar sua voz” dentro do wizard;
- consentimento;
- gravação ou upload;
- validação;
- escuta;
- aprovação;
- nome sugerido “Minha voz”;
- definição automática como padrão.

Se não for possível concluir, o restante do app pode funcionar, mas o TTS permanece pendente e desabilitado.

### Por quê

Sem voz real, o app não pode cumprir o contrato de identidade vocal verificável.

### Rejeitado

**Apenas abrir a biblioteca e deixar o usuário avançar como se estivesse configurado.**
Rejeitado porque isso não conclui a tarefa e mantém o TTS em estado ambíguo.

**Criar uma voz padrão embutida.**
Rejeitado porque viola a identidade real e o consentimento.

---

## D04 — Captura inicial curta e otimizada

### Decisão aceita

A amostra inicial deve capturar identidade, sotaque, articulação e prosódia com o mínimo de áudio útil.

Texto padrão inicial:

> Hoje, João trouxe café quente, pão de queijo, milho e chá. Bia perguntou: amanhã você fala devagar, com clareza, firmeza e emoção?

### Como

- gravar aproximadamente 10 a 12 segundos brutos;
- obter 8 a 10 segundos úteis;
- remover silêncio inicial e final;
- preservar o original;
- derivar referência por engine;
- garantir fala limpa nos primeiros segundos;
- permitir regravação após escuta.

Para Chatterbox, selecionar ou derivar a janela condicionante adequada, respeitando o uso dos primeiros segundos pelo modelo.

### Por quê

Uma gravação longa não gera ganho proporcional no condicionamento e aumenta hesitação, ruído e inconsistência.

### Rejeitado

**Obrigar 20 a 40 segundos para todas as engines.**
Rejeitado porque a necessidade depende do modelo e o Chatterbox usa janelas condicionantes mais curtas.

**Texto genérico “Olá, esta é uma amostra...”**
Rejeitado como padrão final porque possui menor diversidade fonética e prosódica.

---

## D05 — Estilos iniciais são opcionais e a lista é aberta

### Decisão aceita

Oferecer inicialmente:

- neutro;
- acolhedor;
- sério;
- didático;
- entusiasmado;
- reflexivo;
- triste;
- calmo;
- firme;
- narrativo.

O usuário pode criar estilos ilimitados.

### Como

Cada estilo é uma entidade persistida dentro de uma voz e pode conter referência própria, parâmetros, instrução, texto de captura, aliases e compatibilidade por engine.

### Por quê

As necessidades de expressão variam por pessoa e uso. Uma taxonomia fixa não contempla “professor paciente”, “institucional”, “confidencial” ou outros estilos personalizados.

### Rejeitado

**Lista fechada de emoções.**
Rejeitado por limitar o produto.

**Salvar somente CFG e passos no `localStorage`.**
Rejeitado porque isso é preset de parâmetros, não estilo vocal persistente, compartilhável e ligado à voz.

**Chamar a captura de estilo de treinamento.**
Rejeitado porque é condicionamento zero-shot, não fine-tuning.

---

## D06 — Tags usam diretamente o nome do estilo

### Decisão aceita

Sintaxe de estilo:

```text
[acolhedor]
Eu entendo como essa situação pode ser difícil.
[/acolhedor]
```

Com parâmetros opcionais:

```text
[serio intensidade=0.70 ritmo=0.92 pausa_depois=300ms]
Agora precisamos observar este ponto com atenção.
[/serio]
```

Com falante opcional:

```text
[acolhedor falante=ana intensidade=0.60]
Bom dia. Como você está se sentindo hoje?
[/acolhedor]
```

### Como

- a tag resolve um `style_id` ou alias;
- `falante` resolve um speaker cadastrado no roteiro;
- os parâmetros sobrescrevem apenas o segmento;
- o parser remove a marcação antes da engine.

### Por quê

A sintaxe é legível por humanos e mantém o estilo como conceito principal.

### Rejeitado

**`[cmd ...]`.**
Rejeitado por ser verboso e esconder a intenção do texto.

**`[style:acolhedor]`.**
Rejeitado porque foi uma sintaxe provisória e não suporta bem blocos, fechamento, parâmetros e estilos personalizados.

**Enviar tags ao modelo.**
Rejeitado porque Chatterbox PT-BR e VibeVoice não devem ser presumidos como interpretadores dessas tags; elas podem ser pronunciadas ou ignoradas.

---

## D07 — Subtítulos são metadados não falados

### Decisão aceita

Cabeçalhos Markdown organizam o roteiro:

```text
## Introdução

[acolhedor]
Olá. Hoje vamos conversar sobre saúde mental.
[/acolhedor]
```

### Como

- parser reconhece cabeçalhos;
- cria agrupamentos de timeline;
- não envia o título à engine;
- permite reproduzir, regenerar e exportar uma seção.

### Por quê

O usuário precisa organizar roteiros longos sem que a estrutura editorial seja pronunciada.

### Rejeitado

**Tratar toda linha sem tag como fala.**
Rejeitado porque subtítulos e metadados vazariam para o áudio.

---

## D08 — Estilos e múltiplos falantes são implementados por orquestração virtual

### Decisão aceita

Usar a mesma mecânica de jobs por segmento para:

- estilos diferentes da mesma voz;
- múltiplas pessoas ou personagens;
- pausas e eventos;
- regeneração localizada.

### Como

O roteiro:

```text
[acolhedor falante=ana]
Eu entendo sua preocupação.
[/acolhedor]

[serio falante=carlos]
Precisamos revisar os dados.
[/serio]
```

vira dois jobs:

```text
Job 1: voz da Ana + referência acolhedora + parâmetros acolhedores
Job 2: voz do Carlos + referência séria + parâmetros sérios
```

Cada job produz um WAV separado. O montador cria o arquivo final.

### Por quê

Essa é a “gambiarra controlada” necessária para criar virtualmente funções que as engines não oferecem de maneira uniforme ou nativa.

### Rejeitado

**Recompor os segmentos em um único script e mandar tudo de uma vez.**
Rejeitado porque impede referência e parâmetros por trecho, retry localizado, eventos determinísticos e compatibilidade entre engines.

**Afirmar que o modelo entende emoções ou tags.**
Rejeitado por ser tecnicamente incorreto.

**Usar apenas o multi-speaker nativo do VibeVoice como orquestrador universal.**
Rejeitado porque não funciona igual no Chatterbox e não resolve segmentação, eventos e regeneração por trecho.

### Observação sobre modo nativo

O multi-speaker nativo do VibeVoice pode ser preservado como modo avançado ou comparação, mas não substitui o pipeline canônico de orquestração por segmentos.

---

## D09 — Eventos vocais são arquivos separados

### Decisão aceita

Respirações, suspiros e risadas são gravados opcionalmente e inseridos na timeline.

### Como

```text
[respiracao profunda]
[pausa 400ms]
[risada leve]
```

O sistema resolve o evento da voz selecionada e insere o áudio.

### Por quê

É mais previsível do que esperar que uma engine gere um evento paralinguístico não documentado.

### Rejeitado

**Mandar “[respiração]” como texto ao TTS.**
Rejeitado porque pode ser pronunciado literalmente.

**Gerar evento artificial quando não houver gravação.**
Rejeitado porque viola a identidade vocal e a transparência.

---

## D10 — Montagem deve usar timeline, não concatenação bruta

### Decisão aceita

O resultado final é criado por um montador de áudio com manifesto de segmentos.

### Como

- uniformizar sample rate e canais;
- inserir pausas;
- inserir eventos;
- ajustar ganho moderadamente;
- aplicar fades ou crossfades apenas quando apropriados;
- evitar cortar fonemas;
- preservar arquivos intermediários até o job finalizar;
- permitir regenerar um trecho.

### Por quê

`np.concatenate` com silêncio fixo não resolve estalos, volumes divergentes, eventos, estilos ou retry por segmento.

### Rejeitado

**Silêncio fixo de 180 ms entre todos os blocos.**
Rejeitado porque a pausa depende do texto, da tag e da transição.

**Normalização agressiva ou alteração de pitch.**
Rejeitado porque pode degradar identidade e naturalidade.

---

## D11 — Normalização PT-BR ocorre antes da engine e preserva o original

### Decisão aceita

Normalizar texto falável sem alterar o conteúdo original armazenado.

### Como

Cobrir progressivamente:

- números;
- ordinais;
- datas com ano;
- horas;
- moedas;
- percentuais;
- unidades;
- siglas;
- abreviações;
- URLs;
- e-mails;
- telefones;
- versões;
- dicionário de pronúncia editável.

### Por quê

A entrada escrita possui convenções que não correspondem diretamente à fala brasileira.

### Rejeitado

**Reescrever permanentemente o texto do usuário.**
Rejeitado porque perde fidelidade e impede auditoria.

**Aplicar substituições fonéticas globais e irreversíveis.**
Rejeitado porque podem resolver uma engine e piorar outra.

---

## D12 — Chatterbox é a opção preferencial para clonagem natural em PT-BR, mas não altera o padrão automaticamente

### Decisão aceita

Completar Chatterbox com voz de referência e estilos por segmento.

### Como

Expor parâmetros realmente suportados e aplicar referências neutras ou de estilo por job.

### Por quê

É a engine mais alinhada ao requisito de sotaque brasileiro dedicado.

### Rejeitado

**Mudar automaticamente o modelo padrão existente.**
Rejeitado porque o usuário solicitou adicionar, não substituir. A escolha do padrão deve ser explícita.

---

## D13 — VibeVoice 1.5B permanece, mas PT-BR é experimental

### Decisão aceita

Preservar o 1.5B, seus parâmetros reais, condicionamento por voz e capacidade nativa de múltiplos falantes.

### Como

Integrá-lo ao render plan por segmentos e permitir referências de estilo da mesma identidade.

### Por quê

O modelo já possui geração real, long-form e multi-speaker, mas seu comportamento em PT-BR não é equivalente a um checkpoint brasileiro dedicado.

### Rejeitado

**Prometer que referência brasileira corrige completamente o sotaque.**
Rejeitado porque o treinamento linguístico do modelo limita fonologia e prosódia.

---

## D14 — Realtime 0.5B deve permanecer isolado e indisponível até prova nativa

### Decisão aceita

Manter o ADR de subprocesso isolado.

### Como

- ambiente próprio;
- contrato estruturado;
- healthcheck;
- erro sem áudio quando indisponível;
- habilitação somente após PCM/WAV nativo real;
- registrar latência e chunks.

### Por quê

Evita contaminar o runtime principal, que já alterna Transformers padrão e fork vendored.

### Rejeitado

**Atualizar Transformers globalmente para tentar fazê-lo funcionar.**
Rejeitado pelo risco de quebrar VibeVoice 1.5B e ASR.

**Apresentar smoke sintético como TTS.**
Rejeitado porque não prova inferência.

**Prometer clonagem, multi-speaker ou PT-BR.**
Rejeitado até validação específica.

---

## D15 — Large é preservado, mas bloqueado por pré-condições

### Decisão aceita

Manter no catálogo com status e limitações claras.

### Como

- preflight de RAM, VRAM, disco e dependências;
- não carregar em 6 GB quando inviável;
- usar somente referências reais quando houver execução;
- testar contratos por mocks quando não houver hardware.

### Por quê

Preserva evolução futura sem fingir viabilidade no notebook atual.

### Rejeitado

**Criar referência SAPI5 ou senoide para o Large.**
Rejeitado porque viola a política de voz real.

---

## D16 — Dependências incompatíveis são isoladas

### Decisão aceita

Usar processo ou ambiente próprio quando necessário.

### Como

- versões pinadas;
- sem alteração global permanente de `sys.path`;
- sem contaminação de `sys.modules`;
- logs e lifecycle próprios;
- comunicação local estruturada.

### Por quê

O histórico do projeto já mostrou conflitos entre Transformers, `huggingface_hub`, forks e arquiteturas customizadas.

### Rejeitado

**Instalar tudo no mesmo ambiente a qualquer custo.**
Rejeitado porque reduz estabilidade, exatamente o contrário do objetivo local.

---

## D17 — Cancelamento deve ser real

### Decisão aceita

Cada job e segmento deve responder a cancelamento.

### Como

- token de cancelamento;
- checkpoints entre etapas;
- interrupção antes do próximo segmento;
- suporte específico da engine quando disponível;
- limpeza de temporários;
- liberação de VRAM;
- status final correto.

### Por quê

Gerações longas não podem prender recursos ou obrigar o usuário a encerrar o app.

### Rejeitado

**Cancelar apenas a interface enquanto a inferência continua.**
Rejeitado porque não libera memória nem processamento.

---

## D18 — Metadados e manifestos são parte do produto

### Decisão aceita

Toda geração deve ser auditável.

### Como

Registrar por job e segmento:

- engine solicitada e executada;
- checkpoint e revisão;
- dispositivo;
- voz e referência;
- estilo;
- parâmetros;
- seed;
- texto original e normalizado, respeitando privacidade;
- tempos;
- duração;
- RAM e VRAM quando mensuráveis;
- resultado e erro.

### Por quê

É necessário provar que não houve fallback e possibilitar diagnóstico e regeneração.

### Rejeitado

**Confiar apenas no rótulo do seletor da interface.**
Rejeitado porque UI não prova o caminho executado.

---

# 5. Arquitetura-alvo

## 5.1. Camadas

```text
Roteiro original
    ↓
Parser de marcação
    ↓
AST / documento estruturado
    ↓
Resolução de falantes, vozes, estilos e eventos
    ↓
Normalização PT-BR por segmento
    ↓
Render Plan / Timeline
    ↓
Jobs individuais por segmento
    ↓
Adapters de engine
    ↓
WAVs intermediários
    ↓
Montador de áudio
    ↓
WAV final + manifesto
```

## 5.2. Contrato de segmento

Cada segmento deve conter no mínimo:

```text
segment_id
section_id
order
speaker_id
voice_id
style_id
engine_id
original_text
normalized_text
reference_path ou reference_id
parameters
pause_before_ms
pause_after_ms
events_before
events_after
status
seed
output_path
duration_ms
error
```

## 5.3. Estrutura de dados sugerida

```text
data/voices/<voice_id>/
├── profile.json
├── reference.wav
├── original/
├── styles/
│   └── <style_id>/
│       ├── style.json
│       ├── reference.wav
│       ├── original.wav
│       ├── preview/
│       └── engines/
├── events/
│   ├── breath_short.wav
│   ├── breath_deep.wav
│   ├── sigh.wav
│   └── laugh_soft.wav
├── previews/
└── engines/
    ├── vibevoice_1_5b/
    └── chatterbox_pt_br/
```

## 5.4. Separação entre compartilhado e específico

Compartilhado:

- gravação original;
- referência canônica;
- perfil;
- consentimento;
- estilos e eventos como conceitos.

Específico por engine:

- embeddings;
- tokens condicionantes;
- caches;
- previews;
- parâmetros convertidos;
- artefatos derivados.

---

# 6. Estado atual auditado

## 6.1. Entregue e aproveitável

- VibeVoice 1.5B com caminho nativo real;
- embeddings por voz e speaker;
- parâmetros reais do 1.5B;
- ciclo de download e conversão;
- árbitro de VRAM;
- bloqueio honesto do Realtime;
- preflight do Large;
- adapter inicial do Chatterbox PT-BR;
- biblioteca básica de upload, gravação e consentimento;
- endpoint que rejeita fallback comum;
- testes básicos de lifecycle e contratos.

## 6.2. Parcial e precisa ser evoluído

- primeira execução: existe etapa, mas não conclui captura;
- Chatterbox: gera, mas parâmetros são fixos e uma referência é usada para todos os chunks;
- normalização PT-BR: cobre poucos casos;
- orquestração: cria segmentos, mas usa sintaxe antiga e recompõe roteiro;
- estilos: existem apenas como presets de CFG/passos no frontend;
- montagem: concatena chunks com silêncio fixo;
- metadados: bons no 1.5B, incompletos por segmento e no Chatterbox.

## 6.3. Divergente e deve ser removido ou refeito

- presets Windows em `services/voice_profiles.py`;
- SAPI5 em `services/vibevoice_tts_1_5b.py`;
- gerador de senoide no serviço e no worker;
- caminho Large baseado em referências SAPI5/sintéticas;
- `style` persistido apenas no `localStorage`;
- sintaxe `[style:...]`;
- ausência de tags de fechamento;
- ausência de estilos por voz;
- ausência de referências de estilo;
- ausência de subtítulos e eventos;
- concatenação simples em vez de timeline.

## 6.4. Ausente

- falantes virtuais;
- tags dinâmicas baseadas em `style_id`;
- aliases;
- speaker opcional dentro da tag de estilo;
- parser completo;
- AST e render plan;
- regeneração por segmento;
- cancelamento real;
- captura otimizada da primeira voz;
- primeira voz automaticamente padrão;
- estilos personalizados persistentes;
- diálogo multi-voz no Chatterbox por jobs separados;
- eventos de voz;
- montador de áudio adequado;
- relatório final com WAVs e métricas.

---

# 7. Fora de escopo nesta rodada

Para evitar expansão indevida, não incluir agora:

- fine-tuning real do Chatterbox ou VibeVoice;
- treinamento de modelo próprio;
- API ou fallback em nuvem;
- edição espectral avançada;
- clonagem sem consentimento;
- reconhecimento automático perfeito de emoção;
- conversão de voz em tempo real;
- suporte irrestrito a qualquer tag livre gerada por LLM;
- promessa de PT-BR no Realtime 0.5B;
- validação real do Large no hardware de 6 GB;
- reescrita total do aplicativo.

---

# PARTE II — PLANO CONSOLIDADO DE TAREFAS

# 8. Legenda de status e prioridade

- `[x]` aproveitável no estado atual;
- `[~]` parcial, precisa ser corrigido ou ampliado;
- `[ ]` não implementado;
- `P0` bloqueador de confiança ou arquitetura;
- `P1` necessário para o produto-alvo;
- `P2` melhoria posterior ao núcleo funcional.

As tarefas devem ser executadas em fatias pequenas, com TDD quando o comportamento estiver definido. Não iniciar uma tarefa dependente antes de os contratos da predecessora estarem estáveis.

---

# ÉPICO 0 — Baseline, proteção e documentação

## T0.1 — Congelar baseline auditável `[ ]` `P0`

**O que:** registrar commit-base, testes atuais e fixtures de contrato.
**Como:** salvar relatório de testes, catálogo e exemplos de respostas HTTP; criar uma branch de trabalho sem alterar `main`.
**Por quê:** distinguir regressões de problemas já existentes.
**Depende de:** nada.

**Aceite:**

- commit-base registrado;
- testes atuais executados ou limitações documentadas;
- lista de caminhos proibidos encontrada por busca estática;
- nenhum arquivo do usuário descartado.

## T0.2 — Registrar este documento como fonte de verdade `[ ]` `P0`

**O que:** adicionar o documento em `docs/` e referenciá-lo no contexto de domínio.
**Como:** criar ADR ou documento de escopo e marcar a PRD antiga como superseded parcialmente.
**Por quê:** impedir que agentes continuem implementando o escopo reduzido anterior.

**Aceite:**

- `AGENTS.md` ou documento de domínio aponta para esta especificação;
- conflitos com issue antiga estão documentados;
- nenhuma implementação começa sem leitura do documento.

---

# ÉPICO 1 — Remover caminhos proibidos

## T1.1 — Remover presets Windows da biblioteca `[ ]` `P0`

**O que:** excluir `PRESET_VOICES`, aliases legados e exposição na API/UI.
**Como:** migrar configurações antigas para “sem voz configurada” ou voz real existente.
**Por quê:** identidade vocal deve ser real e autorizada.

**Aceite:**

- API lista somente vozes reais;
- seletor não exibe Windows;
- presets legados não resolvem para SAPI;
- migração não apaga vozes do usuário.

## T1.2 — Remover SAPI5 e senoide do runtime `[ ]` `P0`

**O que:** apagar imports, funções e chamadas em todos os adapters e workers.
**Como:** substituir diagnóstico sonoro por erros estruturados, mocks e fixtures estáticas de teste.
**Por quê:** garantir que nenhum áudio falso possa ser apresentado como engine real.

**Aceite:**

- busca por `SAPI`, `win32com`, `System.Speech`, `pyttsx3`, `sine`, `synthetic_smoke` não encontra caminho funcional de produção;
- Large não cria prompt artificial;
- Realtime indisponível retorna apenas erro.

## T1.3 — Criar testes negativos globais `[ ]` `P0`

**O que:** impedir reintrodução dos caminhos proibidos.
**Como:** testes estáticos e de endpoints.
**Por quê:** evitar regressão silenciosa.

**Aceite:**

- teste falha se áudio de outra engine for retornado;
- teste falha se preset Windows reaparecer;
- teste falha se worker retornar áudio sintético.

---

# ÉPICO 2 — Modelo de domínio de vozes, estilos e eventos

## T2.1 — Versionar schema de voz `[~]` `P0`

**O que:** evoluir `profile.json` para schema versionado.
**Como:** incluir referência, original, padrão global, estilos, eventos e estado por engine.
**Por quê:** permitir migração segura e persistência coerente.

**Aceite:**

- `schema_version` presente;
- migração idempotente;
- vozes antigas reais preservadas;
- derivados separados por engine.

## T2.2 — Implementar entidade Style `[ ]` `P1`

**O que:** persistir estilos dentro de cada voz.
**Como:** `style.json`, referência opcional, aliases, parâmetros, instrução e compatibilidade.
**Por quê:** substituir presets globais superficiais por estilos reais.

**Aceite:**

- criar, duplicar, renomear, editar, ordenar, ativar, excluir;
- `style_id` estável;
- nome visível pode mudar;
- referência é opcional;
- exclusão não apaga a voz.

## T2.3 — Implementar entidade Event `[ ]` `P1`

**O que:** armazenar eventos vocais por voz.
**Como:** arquivos e metadados para respiração, suspiro e risada.
**Por quê:** eventos determinísticos e coerentes com a identidade.

**Aceite:**

- gravar, importar, ouvir, substituir e excluir evento;
- evento ausente gera erro de validação do roteiro;
- nenhuma síntese substituta é gerada.

## T2.4 — Importação e exportação segura `[ ]` `P2`

**O que:** exportar voz, estilos e eventos com consentimento.
**Como:** pacote versionado, manifest e detecção de colisão.
**Por quê:** preservar biblioteca local e permitir migração.

---

# ÉPICO 3 — Primeira voz no assistente

## T3.1 — Incorporar captura no wizard `[~]` `P0`

**O que:** transformar a etapa informativa em fluxo real.
**Como:** gravar ou importar sem sair do assistente; consentir; ouvir; regravar; aprovar.
**Por quê:** TTS não pode parecer pronto sem identidade.

**Aceite:**

- primeira voz criada no wizard;
- nome sugerido “Minha voz”;
- voz torna-se padrão automaticamente;
- Chatterbox e VibeVoice que exigem referência aparecem como pendentes sem voz;
- concluir setup não marca TTS como pronto quando pendente.

## T3.2 — Aplicar texto de captura otimizado `[ ]` `P1`

**O que:** substituir frase genérica pelo texto decidido.
**Como:** exibir orientação, destaque de leitura e controles de gravação.
**Por quê:** maximizar informação vocal em poucos segundos.

## T3.3 — Derivar referência canônica por engine `[ ]` `P1`

**O que:** preservar original e criar referência adequada.
**Como:** trim, análise de qualidade, seleção de janela e conversão de formato.
**Por quê:** engines usam janelas e formatos diferentes.

**Aceite:**

- original nunca é perdido;
- referência Chatterbox possui janela útil adequada;
- clipping, silêncio e duração são reportados;
- usuário pode ouvir a referência derivada.

---

# ÉPICO 4 — Linguagem de marcação e parser

## T4.1 — Definir gramática formal `[ ]` `P0`

**O que:** especificar tags de estilo, parâmetros, falante, pausas, eventos e subtítulos.
**Como:** documentar EBNF ou schema equivalente.
**Por quê:** evitar regex incremental e interpretações inconsistentes.

Gramática funcional mínima:

```text
[<style_id> falante=<speaker_id> intensidade=<n> ritmo=<n> ...]
texto
[/<style_id>]

[pausa 400ms]
[respiracao profunda]
## Subtítulo não falado
```

## T4.2 — Implementar parser e AST `[~]` `P0`

**O que:** substituir `_valid_tags={style,pause}` e `_strip_tags`.
**Como:** parser com posição, nós de seção, bloco, evento e texto.
**Por quê:** tags personalizadas e blocos exigem estrutura real.

**Aceite:**

- tags de abertura e fechamento;
- estilo dinâmico;
- aliases;
- parâmetros nomeados;
- `falante` opcional;
- cabeçalhos não falados;
- linha e coluna de erro;
- tags nunca chegam à engine.

## T4.3 — Validar roteiro contra biblioteca `[ ]` `P1`

**O que:** resolver estilos, speakers, vozes e eventos antes de gerar.
**Como:** capability matrix e diagnóstico completo.
**Por quê:** falhar cedo, antes de consumir GPU.

**Aceite:**

- estilo inexistente é erro;
- speaker sem voz é erro;
- evento ausente é erro;
- incompatibilidades são exibidas por segmento;
- nenhuma substituição silenciosa.

---

# ÉPICO 5 — Render plan e falantes virtuais

## T5.1 — Criar RenderPlan persistível `[ ]` `P0`

**O que:** converter AST em timeline de jobs independentes.
**Como:** dataclasses ou schemas versionados, com IDs estáveis.
**Por quê:** separar interpretação de renderização.

**Aceite:**

- cada trecho possui voz, estilo, referência e parâmetros;
- seções e ordem preservadas;
- manifesto serializável;
- texto original e normalizado separados.

## T5.2 — Implementar falantes reais e virtuais `[ ]` `P1`

**O que:** usar o mesmo pipeline para pessoas diferentes e variantes de estilo da mesma voz.
**Como:** speaker resolve voice; style resolve referência e parâmetros.
**Por quê:** esta é a mecânica central definida pelo usuário.

**Aceite:**

- Ana e Carlos podem usar vozes diferentes;
- uma mesma voz pode alternar acolhedor/sério;
- cada trecho gera separadamente;
- interface diferencia falante, voz e estilo.

## T5.3 — Preservar modo nativo VibeVoice como opcional `[ ]` `P2`

**O que:** manter multi-speaker nativo sem confundi-lo com orquestração.
**Como:** modo avançado explicitamente selecionado.
**Por quê:** preservar capacidade existente sem limitar o pipeline comum.

---

# ÉPICO 6 — Normalização PT-BR

## T6.1 — Extrair normalizador modular `[~]` `P1`

**O que:** remover normalização limitada do arquivo de orquestração.
**Como:** módulo com regras testáveis e perfis por engine.
**Por quê:** crescer sem acoplar parser e linguagem.

## T6.2 — Ampliar cobertura `[ ]` `P1`

**Aceite mínimo:**

- datas completas;
- anos;
- horas;
- moedas com singular e plural;
- percentuais;
- unidades;
- siglas configuráveis;
- abreviações;
- URLs, e-mails e telefones;
- números maiores;
- acentuação correta;
- dicionário do usuário.

## T6.3 — Prévia e regras por engine `[ ]` `P2`

**O que:** permitir comparar original e normalizado.
**Por quê:** correções fonéticas podem ser específicas da engine.

---

# ÉPICO 7 — Montador de áudio

## T7.1 — Criar AudioAssembler `[ ]` `P0`

**O que:** substituir concatenação direta.
**Como:** timeline, resample, canais, silêncio, eventos, ganho e fades.
**Por quê:** produzir resultado contínuo e editável.

**Aceite:**

- sample rate uniforme;
- sem estalos evitáveis;
- pausas obedecidas;
- eventos inseridos;
- segmentos preservados;
- manifesto final atualizado.

## T7.2 — Regeneração individual `[ ]` `P1`

**O que:** refazer apenas um segmento.
**Como:** cache de job e remontagem.
**Por quê:** modelos estocásticos podem errar uma frase sem invalidar todo o áudio.

## T7.3 — Transições de estilo `[ ]` `P2`

**O que:** reduzir mudanças abruptas de volume/timbre.
**Como:** ganho moderado e transições configuráveis, sem pitch agressivo.
**Por quê:** referências diferentes da mesma pessoa podem variar.

---

# ÉPICO 8 — Completar Chatterbox PT-BR

## T8.1 — Expor parâmetros reais `[~]` `P1`

**O que:** remover valores fixos do runtime.
**Como:** schema dinâmico para `exaggeration`, `cfg_weight`, `temperature`, `top_p`, `min_p`, `repetition_penalty` e seed quando suportada.
**Por quê:** permitir estilos e experimentação real.

**Aceite:**

- UI mostra apenas parâmetros suportados;
- valores usados aparecem nos metadados;
- parâmetros de tag sobrescrevem apenas o segmento.

## T8.2 — Referência por segmento `[ ]` `P0`

**O que:** não resolver uma única voz/referência para todos os chunks.
**Como:** adapter recebe RenderJob com `reference_path`.
**Por quê:** estilos e múltiplos falantes dependem disso.

## T8.3 — Multi-voz orquestrado `[ ]` `P1`

**O que:** gerar cada fala com a identidade correspondente.
**Como:** jobs separados e AudioAssembler.
**Por quê:** Chatterbox não precisa de multi-speaker nativo para produzir diálogo final.

## T8.4 — Cancelamento e unload `[ ]` `P1`

**O que:** integrar token de cancelamento e limpeza real.
**Aceite:** cancelar antes do próximo segmento e liberar VRAM após job.

## T8.5 — QA PT-BR `[ ]` `P1`

**O que:** gerar amostras neutra, estilos, números e texto longo.
**Como:** comparação auditiva e round-trip apenas como sinal auxiliar.
**Por quê:** inteligibilidade não equivale a naturalidade.

---

# ÉPICO 9 — Integrar VibeVoice ao RenderPlan

## T9.1 — Adaptar 1.5B para jobs por segmento `[~]` `P1`

**O que:** receber texto limpo, voz e referência/embedding resolvidos.
**Como:** preservar caminho nativo e parâmetros auditados.
**Por quê:** participar da mesma linguagem de orquestração.

## T9.2 — Referências de estilo experimentais `[ ]` `P1`

**O que:** permitir estilo da mesma voz no 1.5B.
**Como:** embeddings separados por referência e cache com hash.
**Por quê:** criar variações virtuais sem alegar emoção nativa.

## T9.3 — Corrigir Large para vozes reais `[ ]` `P0`

**O que:** eliminar `_build_voice_samples` artificial.
**Como:** usar biblioteca e referências reais ou permanecer indisponível.
**Por quê:** cumprir contrato de identidade.

## T9.4 — Preservar limitações PT-BR `[ ]` `P1`

**O que:** rotular 1.5B como PT-BR experimental.
**Por quê:** evitar promessas que o modelo não sustenta.

---

# ÉPICO 10 — Realtime 0.5B isolado

## T10.1 — Remover synthetic smoke do runtime `[ ]` `P0`

**O que:** worker nunca retorna senoide.
**Como:** transporte validado por testes sem áudio de produção.
**Por quê:** smoke não é inferência.

## T10.2 — Concluir adapter nativo no subprocesso `[~]` `P2`

**O que:** carregar arquitetura streaming e produzir PCM real.
**Como:** ambiente isolado conforme ADR.
**Aceite:** áudio audível, chunks reais, latência e metadata.

## T10.3 — Capability matrix do Realtime `[ ]` `P2`

**O que:** declarar apenas voz incorporada e controles comprovados.
**Por quê:** não assumir clonagem, estilo, multi-speaker ou PT-BR.

---

# ÉPICO 11 — Interface e experiência

## T11.1 — Biblioteca unificada por engine `[~]` `P1`

**O que:** remover rótulo exclusivo “VibeVoice 1.5B”.
**Como:** voz é global; compatibilidade e previews são por engine.
**Por quê:** Chatterbox é engine adicional da mesma biblioteca.

## T11.2 — Gerenciador de estilos `[ ]` `P1`

**O que:** UI para criar, gravar, editar, testar e excluir estilos.
**Aceite:** estilos iniciais opcionais e estilos livres do usuário.

## T11.3 — Editor de roteiro `[ ]` `P1`

**O que:** syntax highlight, autocomplete dinâmico e validação.
**Como:** carregar styles/aliases/events da voz e speakers do roteiro.
**Por quê:** reduzir erro de marcação.

## T11.4 — Timeline e segmentos `[ ]` `P1`

**O que:** visualizar seção, falante, estilo, status e áudio por segmento.
**Aceite:** reproduzir e regenerar individualmente.

## T11.5 — Parâmetros por engine `[~]` `P1`

**O que:** esconder controles incompatíveis.
**Por quê:** hoje o frontend mistura parâmetros do 1.5B com outras engines.

---

# ÉPICO 12 — Jobs, cancelamento e recursos

## T12.1 — Job pai e jobs de segmento `[ ]` `P0`

**O que:** modelar renderização composta.
**Como:** job pai agrega progresso e segmentos.
**Por quê:** permitir retry, cancelamento e status preciso.

## T12.2 — Cancelamento cooperativo `[ ]` `P1`

**O que:** cancelar pipeline e impedir próximo segmento.
**Como:** token consultado pelo orquestrador, assembler e adapters.
**Aceite:** temporários removidos e VRAM liberada.

## T12.3 — Integração completa com ResourceArbiter `[~]` `P1`

**O que:** registrar jobs e transições de engine.
**Por quê:** evitar OOM ao alternar Whisper, VibeVoice e Chatterbox.

---

# ÉPICO 13 — Metadados, privacidade e observabilidade

## T13.1 — Manifesto de renderização `[ ]` `P1`

**O que:** arquivo JSON ao lado do WAV ou registro de job.
**Por quê:** provar engine e permitir regeneração.

## T13.2 — Metadados por segmento `[~]` `P1`

**O que:** engine, checkpoint, dispositivo, voz, estilo, referência, parâmetros, seed, tempo e duração.
**Por quê:** auditoria e diagnóstico.

## T13.3 — Higienizar logs `[~]` `P1`

**O que:** não registrar áudio, texto privado integral ou caminhos sensíveis.
**Como:** IDs, hashes curtos e mensagens estruturadas.

## T13.4 — Exclusão completa `[ ]` `P1`

**O que:** apagar voz, estilos, eventos e derivados.
**Por quê:** privacidade e consentimento revogável.

---

# ÉPICO 14 — Testes e validação final

## T14.1 — Testes unitários de domínio e parser `[ ]` `P0`

Cobrir:

- tags diretas;
- parâmetros;
- falante opcional;
- aliases;
- tags de fechamento;
- subtítulos;
- eventos;
- erros com linha/coluna;
- render plan;
- normalização.

## T14.2 — Testes de integração das engines `[~]` `P1`

Cobrir:

- engine solicitada = executada;
- voz por segmento;
- estilo por segmento;
- ausência de fallback;
- Chatterbox e VibeVoice independentes;
- Large bloqueado;
- Realtime indisponível sem áudio.

## T14.3 — Testes do AudioAssembler `[ ]` `P1`

Cobrir:

- ordem;
- sample rate;
- canais;
- pausas;
- eventos;
- fades;
- regeneração;
- cancelamento;
- arquivo final íntegro.

## T14.4 — QA real no hardware-alvo `[ ]` `P1`

Gerar no mínimo:

1. Chatterbox neutro;
2. Chatterbox acolhedor;
3. Chatterbox estilo criado pelo usuário;
4. Chatterbox com dois falantes;
5. VibeVoice 1.5B neutro;
6. VibeVoice 1.5B com duas referências de estilo;
7. roteiro com subtítulos, pausa e respiração;
8. números, datas, moeda e siglas;
9. texto longo segmentado;
10. regeneração de um trecho.

## T14.5 — Relatório final `[ ]` `P1`

Incluir:

- WAVs;
- engine real;
- checkpoint;
- dispositivo;
- voz;
- estilo;
- parâmetros;
- latência;
- fator de tempo real;
- RAM/VRAM;
- limitações;
- testes não executados.

---

# 9. Sequência recomendada de execução

## Fase A — Restaurar confiança

1. T0.1
2. T0.2
3. T1.1
4. T1.2
5. T1.3
6. T9.3
7. T10.1

**Gate A:** nenhuma referência funcional a SAPI5, senoide ou voz Windows.

## Fase B — Consolidar dados e primeira voz

1. T2.1
2. T2.2
3. T2.3
4. T3.1
5. T3.2
6. T3.3

**Gate B:** instalação cria uma voz real padrão e estilos podem ser persistidos.

## Fase C — Orquestração verdadeira

1. T4.1
2. T4.2
3. T4.3
4. T5.1
5. T5.2
6. T6.1
7. T6.2
8. T7.1

**Gate C:** roteiro com tags vira jobs separados e WAV final montado.

## Fase D — Engines

1. T8.1
2. T8.2
3. T8.3
4. T8.4
5. T9.1
6. T9.2
7. T9.4

**Gate D:** Chatterbox e VibeVoice usam o mesmo RenderPlan sem trocar de engine.

## Fase E — UX e operação

1. T11.1
2. T11.2
3. T11.3
4. T11.4
5. T11.5
6. T12.1
7. T12.2
8. T12.3
9. T13.1
10. T13.2

**Gate E:** usuário cria voz/estilo, escreve roteiro e regenera segmentos pela interface.

## Fase F — Realtime, QA e fechamento

1. T10.2
2. T10.3
3. T14.1
4. T14.2
5. T14.3
6. T14.4
7. T14.5

**Gate F:** apenas capacidades realmente validadas aparecem como disponíveis.

---

# 10. Definition of Done global

O escopo só está concluído quando:

- não existe SAPI5, voz Windows ou senoide em produção;
- não existe fallback de engine ou identidade;
- primeira voz é criada ou importada no wizard e vira padrão;
- Chatterbox é uma engine adicional PT-BR verificável;
- estilos iniciais são opcionais;
- estilos personalizados pertencem à voz e podem possuir referência;
- tags usam diretamente o nome do estilo;
- `falante` pode ser indicado como parâmetro da tag;
- subtítulos não são pronunciados;
- tags nunca chegam à engine;
- cada trecho é gerado separadamente;
- falantes reais e virtuais usam o mesmo pipeline;
- eventos são inseridos deterministicamente;
- o áudio final é montado por timeline;
- um segmento pode ser regenerado;
- cancelamento libera recursos;
- VibeVoice 1.5B permanece disponível e transparente sobre PT-BR experimental;
- Realtime só é habilitado após áudio nativo real;
- Large não usa referência artificial;
- normalização PT-BR preserva texto original;
- metadados provam a engine e voz usadas;
- testes e WAVs reais sustentam as declarações da interface.

---

# 11. Instrução curta para o agente executor

Leia integralmente este documento antes de planejar ou editar. Não use a PRD antiga como limite do escopo. Trabalhe em uma tarefa por vez, respeitando dependências e gates. Para cada tarefa, apresente primeiro o entendimento de “o que, como e por quê”, confirme quais decisões já estão fechadas, implemente com testes e não introduza alternativa rejeitada. Não faça commit, push, release ou deploy sem autorização explícita.
