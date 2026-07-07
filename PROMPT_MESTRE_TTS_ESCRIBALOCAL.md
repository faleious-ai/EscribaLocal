# Prompt mestre — conclusão do TTS VibeVoice e integração do Chatterbox PT-BR no EscribaLocal

## Papel do agente

Você é o agente desenvolvedor responsável por concluir a implementação de TTS do EscribaLocal no estado atual do repositório.

Não reescreva o aplicativo do zero. Não descarte alterações existentes. Não faça commit, push, release ou publicação.

Antes de editar:

1. Leia `AGENTS.md`.
2. Leia `CONTEXT.md`, quando existir.
3. Leia os documentos aplicáveis em `docs/`, incluindo ADRs.
4. Leia todo o fluxo atual de TTS, biblioteca de vozes, instalador, primeira execução, catálogo de modelos, gerenciamento de recursos, frontend, rotas, testes e logs.
5. Verifique `git status` e preserve alterações existentes.
6. Identifique exatamente quais partes já estão implementadas, quais estão incompletas e quais apenas simulam funcionamento.
7. Reproduza os erros atuais antes de corrigi-los.
8. Use as skills e convenções já definidas no repositório.

O objetivo não é apenas “fazer gerar algum áudio”. O objetivo é tornar o TTS local verificável, transparente, modular, persistente e adequado ao português brasileiro.

---

# 1. Objetivo geral

Concluir o suporte aos modelos VibeVoice já existentes e, depois de estabilizá-los, integrar o Chatterbox PT-BR como um novo modelo TTS selecionável.

A arquitetura final deve possuir:

- VibeVoice 1.5B;
- VibeVoice Realtime 0.5B;
- VibeVoice Large;
- Chatterbox PT-BR;
- biblioteca de identidades vocais criada pelo usuário;
- estilos opcionais pertencentes a cada voz;
- estilos personalizados criados pelo usuário;
- eventos vocais opcionais;
- linguagem de marcação própria do EscribaLocal;
- segmentação e montagem de áudio;
- normalização textual PT-BR;
- gerenciamento explícito de CPU, RAM, GPU e VRAM;
- falhas explícitas, sem fallback silencioso;
- metadados que provem qual engine gerou cada áudio.

O Chatterbox deve ser adicionado como outra engine. Ele não deve substituir, remover ou alterar silenciosamente os modelos VibeVoice.

Não mude o modelo padrão atual, salvo se já existir uma decisão arquitetural registrada no repositório.

---

# 2. Regras arquiteturais obrigatórias

## 2.1. Funcionamento 100% local

Toda a inferência, clonagem, armazenamento, normalização, processamento e montagem deve ocorrer localmente.

Não utilizar:

- API externa;
- serviço remoto;
- telemetria de voz;
- envio de gravação;
- envio de embedding;
- fallback em nuvem.

O download inicial dos pesos pode usar as fontes oficiais configuradas pelo projeto. Depois do download, a geração deve funcionar offline.

## 2.2. Proibição total de fallback

Remova 100% do fallback SAPI5.

Exclua do código de produção:

- SAPI5;
- `pyttsx3`;
- `System.Speech`;
- vozes do Windows;
- adaptadores de voz do sistema;
- geração de senoide;
- áudio artificial de diagnóstico usado como se fosse TTS;
- silêncio gerado como falsa resposta;
- troca automática de engine;
- troca automática de checkpoint;
- retorno HTTP 200 com áudio produzido por outro mecanismo.

Uma solicitação para uma engine deve ser atendida exclusivamente pela engine solicitada.

Se a engine falhar:

- interrompa a operação;
- retorne erro claro;
- registre a causa real;
- preserve o traceback nos logs técnicos;
- não gere áudio substituto.

Os metadados de toda geração devem informar:

- engine solicitada;
- engine efetivamente executada;
- checkpoint;
- revisão do checkpoint;
- dispositivo real;
- precisão ou quantização usada;
- voz selecionada;
- estilo selecionado;
- referência de áudio usada;
- seed;
- parâmetros reais;
- duração do áudio;
- tempo total;
- sucesso ou erro.

Adicione testes que falhem caso referências funcionais a SAPI5, senoide ou fallback automático reapareçam no código de produção.

## 2.3. Sem vozes padrão distribuídas

Remova:

- vozes padrão incluídas no aplicativo;
- vozes do Windows;
- presets que se apresentam como identidades vocais;
- nomes genéricos como “Masculina”, “Feminina”, “Narrador” ou “Profissional” quando representarem uma voz embutida.

Diferencie claramente:

- **voz**: identidade vocal criada a partir de gravação ou áudio importado;
- **estilo**: forma de falar aplicada à identidade vocal;
- **preset**: conjunto editável de parâmetros;
- **evento vocal**: respiração, suspiro, risada ou outro áudio curto;
- **engine**: modelo TTS responsável pela inferência.

Presets de estilo podem existir. Presets de voz embutida não podem existir.

---

# 3. Ordem obrigatória de implementação

Execute nesta ordem:

1. Diagnosticar e concluir VibeVoice 1.5B.
2. Diagnosticar e implementar corretamente VibeVoice Realtime 0.5B.
3. Preservar e completar o adaptador VibeVoice Large.
4. Remover integralmente SAPI5, senoide, vozes padrão e fallbacks.
5. Consolidar biblioteca de vozes e primeira execução.
6. Implementar estilos, eventos e linguagem de marcação.
7. Implementar normalização PT-BR e renderização segmentada.
8. Integrar Chatterbox PT-BR como nova engine.
9. Executar testes de regressão de VibeVoice, Whisper, VibeVoice ASR e demais módulos.
10. Gerar exemplos reais e relatório final.

Não implemente o Chatterbox antes de compreender e estabilizar a arquitetura atual do VibeVoice.

---

# 4. Diagnóstico inicial obrigatório

Reproduza separadamente:

- carregamento do VibeVoice 1.5B;
- geração do VibeVoice 1.5B;
- carregamento do Realtime 0.5B;
- streaming do Realtime 0.5B;
- carregamento do Large;
- seleção e aplicação de voz personalizada;
- uso de parâmetros avançados;
- cancelamento;
- descarregamento;
- geração multifalante;
- geração em CPU;
- geração em CUDA.

Para cada caso:

- capture o traceback completo;
- identifique a causa raiz;
- diferencie erro de dependência, arquitetura, checkpoint, memória, dispositivo, voz e inferência;
- confirme se o áudio veio realmente da engine solicitada;
- não considere fallback como sucesso;
- registre a versão efetiva de Python, Torch, CUDA, Transformers, Hugging Face Hub, Accelerate, BitsAndBytes e bibliotecas específicas.

Investigue especialmente:

- contaminação entre `custom_transformers` e Transformers padrão;
- versões vendored antigas de `huggingface_hub`;
- alterações permanentes em `sys.path`;
- arquiteturas `vibevoice` e `vibevoice_streaming` não reconhecidas;
- divergência entre configuração e checkpoint;
- conversão incompleta;
- cache contaminado;
- tentativa de usar `pipeline("text-to-speech")` em arquitetura não suportada;
- falhas mascaradas por fallback.

Não faça upgrade amplo de dependências sem demonstrar por que ele é necessário.

---

# 5. Conclusão do VibeVoice 1.5B

## 5.1. Download, conversão e estados

Finalize:

- download;
- verificação de integridade;
- conversão local, quando necessária;
- detecção da conversão;
- retomada após interrupção;
- remoção;
- atualização de status;
- carregamento;
- descarregamento.

Estados mínimos:

- não instalado;
- baixando;
- baixado sem conversão;
- convertendo;
- pronto;
- carregando;
- carregado;
- descarregando;
- erro.

A conversão deve poder ser acionada pelo gerenciador de modelos ou interface. O usuário não deve precisar descobrir um comando oculto.

## 5.2. Inferência real

Use o caminho nativo compatível com o checkpoint e com a implementação upstream.

Não use uma pipeline genérica incompatível.

Valide:

- CPU;
- CUDA;
- falta de VRAM;
- falta de RAM;
- checkpoint corrompido;
- voz inválida;
- texto vazio;
- cancelamento.

Quando não houver memória suficiente:

- respeite a política explicitamente selecionada pelo usuário;
- permita falhar;
- permita CPU apenas como opção explícita;
- nunca troque de engine.

## 5.3. Voz personalizada

Confirme que o `reference.wav` e os artefatos derivados são realmente usados.

Implemente ou valide:

- gravação;
- upload;
- escuta da referência;
- substituição;
- regravação;
- hash;
- duração;
- formato;
- revisão;
- cache;
- invalidação;
- preview por engine;
- exclusão;
- definição como padrão.

Embeddings, condicionamentos e caches devem ser invalidados quando:

- a referência mudar;
- o arquivo mudar;
- o hash mudar;
- a revisão do modelo mudar;
- a configuração relevante mudar.

Não reutilize embeddings entre engines.

## 5.4. Multifalante

Preserve e teste:

- voz única;
- diálogo multifalante;
- associação entre `Speaker N` e uma voz;
- vozes diferentes por falante;
- falante ausente;
- duplicidade;
- troca de voz;
- inconsistência de referência.

Confirme nos logs e metadados quais referências foram usadas por falante.

## 5.5. Parâmetros

Verifique quais parâmetros têm efeito real.

Preserve apenas quando suportados:

- `cfg_scale`;
- `n_diffusion_steps`;
- `max_frames`;
- `seed`;
- dispositivo;
- precisão;
- política de memória;
- velocidade.

Quando velocidade for pós-processamento:

- identifique isso na interface;
- registre nos metadados;
- permita desativar;
- preserve o tom quando possível;
- informe perda potencial de qualidade.

Não exponha como funcional um parâmetro ignorado.

## 5.6. Cancelamento

Implemente cancelamento real:

- sinal de cancelamento;
- interrupção entre etapas;
- encerramento limpo;
- exclusão de temporários;
- liberação de referências;
- coleta de lixo;
- limpeza de cache CUDA;
- atualização correta do status.

---

# 6. VibeVoice Realtime 0.5B

## 6.1. Implementação nativa

Implemente usando a arquitetura própria compatível com `vibevoice_streaming`.

Não use `pipeline("text-to-speech")` genérica.

Pesquise e use:

- código upstream;
- classe correta;
- processador correto;
- formato correto de voz incorporada;
- geração em streaming real;
- contrato de cache;
- descarregamento.

Se houver incompatibilidade de dependências com o processo principal, use:

- ambiente Python isolado;
- subprocesso local;
- servidor somente em `127.0.0.1`;
- contrato estável entre aplicação e engine.

Não contamine o ambiente de Whisper, VibeVoice ASR ou das demais engines.

## 6.2. Limitações reais

O Realtime deve ser tratado como engine distinta.

Não declare suporte a:

- clonagem da voz do usuário;
- `reference.wav`;
- estilos gravados pelo usuário;
- multifalante;
- PT-BR garantido;
- emoção nativa não documentada.

Use apenas vozes incorporadas oficialmente suportadas.

A voz portuguesa experimental deve ser identificada como:

> Português experimental — variante regional não garantida

Não a apresente como PT-BR sem validação auditiva e documental.

## 6.3. Streaming

Implemente streaming verdadeiro pelo WebSocket existente.

Registre:

- engine;
- checkpoint;
- dispositivo;
- voz incorporada;
- latência até o primeiro áudio;
- tamanho dos chunks;
- duração;
- cancelamento;
- desconexão;
- erro.

Não envie SAPI5, senoide, silêncio sintético ou áudio de outra engine.

Só habilite a opção na interface depois de uma geração nativa real passar nos testes.

---

# 7. VibeVoice Large

Preserve o modelo como opção separada.

Complete:

- adaptador;
- download;
- carregamento;
- verificação;
- status;
- descarregamento;
- erros.

Antes de carregar, verifique:

- VRAM;
- RAM;
- espaço em disco;
- dispositivo;
- precisão;
- compatibilidade.

Na RTX 3050 de 6 GB:

- não o apresente como recomendado;
- não tente carregar cegamente;
- bloqueie com explicação objetiva quando inviável;
- não trave o aplicativo;
- não declare validado sem evidência.

Teste por mocks, contratos e funções puras quando o hardware não permitir geração real.

---

# 8. Isolamento de dependências

Elimine a contaminação entre engines.

Regras:

- não alterar `sys.path` globalmente de forma permanente;
- não sobrescrever módulos globais;
- não compartilhar ambiente incompatível por conveniência;
- não atualizar Torch ou Transformers globalmente sem necessidade comprovada;
- usar versões pinadas;
- documentar cada pin;
- automatizar a preparação do ambiente;
- validar o ambiente antes de iniciar a engine;
- expor erros de ambiente separadamente.

Quando necessário, cada engine pode possuir:

- ambiente virtual próprio;
- processo local próprio;
- cache próprio;
- logs próprios.

A interface do EscribaLocal deve permanecer única.

---

# 9. Gerenciamento de recursos

Integre todas as engines ao `resource_arbiter` ou mecanismo equivalente.

Antes de carregar uma engine:

- verificar RAM;
- verificar VRAM;
- verificar engine ocupante;
- descarregar engines incompatíveis;
- aguardar liberação;
- limpar referências;
- executar coleta de lixo;
- limpar cache CUDA.

Mostre na interface:

- engine carregada;
- dispositivo;
- RAM estimada;
- VRAM estimada;
- RAM real, quando mensurável;
- VRAM real, quando mensurável;
- modelo;
- revisão;
- precisão;
- estado.

Não permita cargas incompatíveis simultâneas na RTX 3050 de 6 GB.

---

# 10. Primeira voz durante a instalação ou primeira execução

## 10.1. Regra geral

O aplicativo não possui voz de fábrica.

Na instalação nova ou primeira execução, adicione uma etapa obrigatória:

> Criar sua voz

O TTS só será considerado configurado depois que uma voz real do usuário for criada.

Se o microfone estiver indisponível:

- permita concluir os demais módulos;
- marque o TTS como configuração pendente;
- mantenha geração TTS desabilitada;
- reabra o assistente depois.

## 10.2. Consentimento

Antes de gravar, informe:

- a gravação será usada para clonagem local;
- o processamento ocorre localmente;
- o armazenamento ocorre localmente;
- nenhum áudio será enviado a serviços externos;
- o usuário deve gravar a própria voz ou possuir autorização.

Exija confirmação explícita e armazene-a localmente.

## 10.3. Texto mínimo de captura

Use como texto inicial:

> Hoje, João trouxe café quente, pão de queijo, milho e chá. Bia perguntou: amanhã você fala devagar, com clareza, firmeza e emoção?

Este texto deve ser tratado como configuração padrão editável do projeto.

A captura inicial deve priorizar qualidade condicionante, não duração arbitrária.

Para Chatterbox PT-BR:

- alvo de 8 a 10 segundos úteis;
- permitir aproximadamente 10 a 12 segundos brutos;
- remover silêncio inicial e final;
- garantir fala limpa nos primeiros segundos;
- preservar o original;
- selecionar o melhor trecho contínuo quando necessário.

Para outras engines, mantenha a gravação original completa e derive a versão adequada por engine.

Não inclua no trecho condicionado:

- contagem regressiva;
- instruções;
- hesitação;
- pigarro;
- ruído inicial;
- respiração inicial forte;
- silêncio excessivo.

## 10.4. Interface de gravação

Mostrar:

- microfone selecionado;
- troca de microfone;
- nível de entrada;
- duração;
- indicador de clipping;
- indicador de silêncio;
- iniciar;
- parar;
- ouvir;
- gravar novamente;
- aprovar.

Orientações:

- use sua voz normal;
- não imite locutor;
- não force emoção;
- mantenha distância constante;
- leia naturalmente;
- evite ruído;
- não use música.

## 10.5. Validação

Validar:

- áudio não vazio;
- duração mínima;
- duração útil;
- clipping;
- volume;
- silêncio;
- relação sinal/ruído;
- reverberação excessiva;
- taxa de amostragem;
- canais;
- formato;
- presença de apenas um falante, quando tecnicamente possível.

Não rejeitar automaticamente apenas por uma métrica imperfeita. Permita revisão auditiva.

## 10.6. Criação do perfil

Após aprovação:

- criar a voz;
- sugerir o nome “Minha voz”;
- permitir renomear;
- salvar a referência;
- calcular hash;
- salvar metadados;
- definir como voz padrão global;
- selecionar inicialmente em engines compatíveis;
- preparar artefatos por engine sob demanda.

Estrutura base:

```text
data/voices/<voice_id>/
├── profile.json
├── reference.wav
├── original/
├── styles/
├── events/
├── preview/
└── engines/
    ├── vibevoice/
    └── chatterbox_pt_br/
```

## 10.7. Sem voz configurada

Quando não houver voz:

- mostrar “Nenhuma voz configurada”;
- desabilitar geração TTS;
- direcionar para criação de voz;
- não selecionar voz embutida;
- não usar voz do sistema;
- não trocar de engine.

Ao excluir a última voz:

- confirmar;
- excluir referências e derivados;
- desabilitar TTS;
- abrir fluxo de criação.

## 10.8. Migração

Em atualizações:

- preservar vozes reais do usuário;
- remover somente vozes embutidas, Windows ou artificiais;
- não apagar gravações pessoais;
- pedir seleção da voz padrão quando necessário;
- abrir o assistente quando não houver voz real.

---

# 11. Biblioteca de vozes

A biblioteca deve permitir:

- gravar nova voz;
- importar áudio;
- ouvir referência;
- renomear;
- regravar;
- substituir referência;
- definir padrão;
- excluir;
- exportar;
- importar;
- gerar preview por engine;
- verificar artefatos preparados;
- invalidar caches;
- reconstruir derivados.

O `reference.wav` pode ser compartilhado entre engines.

Não compartilhar:

- embedding;
- condicionamento;
- tokens;
- cache;
- preview;
- metadados específicos da engine.

---

# 12. Estilos de fala

## 12.1. Conceito

Estilo pertence a uma voz.

Não trate estilo como outra identidade vocal.

Não chame a criação de referência de estilo de treinamento ou fine-tuning. Use:

- referência de estilo;
- perfil de estilo;
- condicionamento;
- preset.

## 12.2. Estilos iniciais opcionais

Disponibilize como modelos opcionais:

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

Esses estilos:

- não são obrigatórios;
- não são uma lista fechada;
- não devem ser restaurados automaticamente após exclusão;
- não devem criar gravações sozinhos;
- não devem ser apresentados como capacidades universais;
- podem ser ignorados;
- podem ser editados;
- podem ser duplicados;
- podem ser excluídos.

Na instalação, exija apenas a amostra neutra.

## 12.3. Estilos personalizados

Permita criar estilos ilimitados.

Campos:

- nome;
- `style_id`;
- descrição;
- instrução de interpretação;
- texto de gravação;
- cor ou ícone opcional;
- parâmetros padrão;
- referência opcional;
- aliases;
- ordem;
- compatibilidade por engine;
- status ativo;
- origem.

Exemplos:

- irônico;
- preocupado;
- empolgado contido;
- professor paciente;
- locução institucional;
- suspense;
- notícia urgente;
- conversa informal;
- atendimento terapêutico;
- leitura infantil;
- cansado;
- indignado;
- confidencial.

Não imponha taxonomia fechada.

## 12.4. Estrutura

```text
data/voices/<voice_id>/styles/<style_id>/
├── style.json
├── reference.wav
├── original.wav
├── preview/
└── engines/
    ├── chatterbox_pt_br/
    └── vibevoice/
```

O `style.json` deve registrar:

- identificador estável;
- nome;
- descrição;
- aliases;
- parâmetros;
- referência;
- hash;
- criação;
- modificação;
- engines;
- origem;
- habilitação;
- ordem;
- compatibilidade.

Renomear o estilo não deve alterar o identificador interno.

## 12.5. Assistente opcional de captura

Ofereça depois da instalação:

> Capturar estilos da minha voz

Texto-base sugerido:

> Hoje eu quero explicar uma ideia importante. Observe cada detalhe, respire com calma e siga comigo até o final.

Instruções iniciais:

- acolhedor: próximo e tranquilizador;
- entusiasmado: alegre e energético sem gritar;
- sério: firme e controlado;
- didático: claro e explicativo;
- reflexivo: lento e contemplativo;
- triste: energia reduzida sem teatralização excessiva.

Permita:

- editar instrução;
- editar texto;
- usar texto padronizado;
- usar texto personalizado;
- gravar;
- importar;
- ouvir;
- comparar com neutro;
- repetir;
- aprovar;
- excluir.

As referências devem preferencialmente ser gravadas:

- pela mesma pessoa;
- no mesmo ambiente;
- com o mesmo microfone;
- à mesma distância;
- com ganho semelhante.

## 12.6. Estilo sem referência própria

Quando não houver referência, permita explicitamente:

- usar referência neutra;
- usar somente parâmetros;
- escolher uma referência de outro estilo.

Nunca reutilize outra referência silenciosamente.

---

# 13. Eventos vocais

Eventos não são estilos.

Permita gravar opcionalmente:

- respiração curta;
- respiração profunda;
- suspiro;
- risada leve.

Estrutura:

```text
data/voices/<voice_id>/events/
├── breath_short.wav
├── breath_deep.wav
├── sigh.wav
└── laugh_soft.wav
```

Insira eventos deterministicamente na linha do tempo.

Quando o evento não existir:

- mostrar indisponível;
- não gerar substituto;
- não pronunciar o nome;
- não ignorar silenciosamente.

Não inclua eventos na referência neutra.

---

# 14. Linguagem de marcação do EscribaLocal

## 14.1. Regra

As tags pertencem ao EscribaLocal.

Nunca enviar tags literalmente ao tokenizer ou à engine.

Não usar `[cmd]`.

A tag deve ser o nome do estilo.

## 14.2. Sintaxe

```text
[acolhedor]
Eu entendo como essa situação pode ser difícil.
[/acolhedor]

[serio intensidade=0.70 ritmo=0.92 pausa_depois=300ms]
Agora precisamos observar este ponto com atenção.
[/serio]

[pausa 450ms]

[entusiasmado intensidade=0.80]
A boa notícia é que conseguimos resolver!
[/entusiasmado]

[respiracao profunda]
```

Estilo personalizado:

```text
[professor_paciente intensidade=0.65 ritmo=0.92]
Vamos dividir o problema em etapas.
[/professor_paciente]
```

## 14.3. Parâmetros universais

Suportar inicialmente:

- `intensidade`;
- `ritmo`;
- `temperatura`;
- `seed`;
- `pausa_antes`;
- `pausa_depois`;
- `volume`.

Parâmetros omitidos usam o preset salvo.

Sobrescritas na tag afetam apenas o trecho atual.

## 14.4. Parâmetros específicos

Permita parâmetros específicos somente quando:

- a engine realmente os suportar;
- estiverem cadastrados no schema da engine;
- forem validados;
- forem exibidos como avançados.

Nunca invente suporte.

## 14.5. Tags dinâmicas

A tag deve derivar do `style_id`.

Exemplo:

- “Locução Institucional” → `locucao_institucional`;
- “Professor Paciente” → `professor_paciente`.

Permita aliases:

- `[institucional]`;
- `[corporativo]`.

Regras:

- sem espaços;
- sem colisão;
- normalização consistente;
- nome visível pode ter acentos;
- tag não precisa de acento;
- comparação sem diferenciar maiúsculas e minúsculas;
- colisão com eventos é proibida.

O frontend não deve conter lista fixa de estilos.

Carregue dinamicamente:

- estilos ativos;
- aliases;
- eventos disponíveis.

## 14.6. Parser

O parser deve:

- gerar estrutura ou AST;
- preservar texto original;
- gerar texto limpo;
- indicar segmentos;
- validar abertura e fechamento;
- apontar linha e coluna;
- rejeitar tags desconhecidas;
- rejeitar parâmetros inválidos;
- limitar valores;
- impedir aninhamento de estilos na primeira versão;
- nunca pronunciar tag inválida;
- não ignorar erro silenciosamente.

---

# 15. Aplicação dos estilos por engine

## 15.1. Chatterbox PT-BR

Para cada segmento:

- selecionar referência do estilo;
- usar referência neutra somente quando configurado;
- mapear intensidade para `exaggeration`, quando aplicável;
- aplicar `cfg_weight`;
- aplicar `temperature`;
- aplicar `top_p`;
- aplicar `min_p`;
- aplicar `repetition_penalty`;
- aplicar seed;
- registrar valores reais.

Não trate `exaggeration` como emoção categórica.

## 15.2. VibeVoice 1.5B

Aplicar estilos de forma experimental por:

- referências separadas da mesma pessoa;
- variantes internas de speaker, quando apropriado;
- parâmetros realmente disponíveis;
- segmentação;
- múltiplas seeds;
- seleção A/B.

Identificar claramente:

> condicionamento experimental por referência

Não declarar suporte nativo a emoção.

Não declarar PT-BR estável sem evidência.

## 15.3. Realtime 0.5B

Usar somente recursos reais.

Não associar:

- referências clonadas;
- estilos gravados;
- eventos condicionantes;
- identidade do usuário.

Tags podem controlar somente:

- segmentação;
- pausas;
- parâmetros suportados;
- voz incorporada;
- pós-processamento explicitamente identificado.

Quando estilo não for suportado:

- informar incompatibilidade antes de gerar;
- não simular;
- não trocar para neutro silenciosamente;
- permitir escolha explícita do usuário.

---

# 16. Normalização textual PT-BR

Crie um módulo compartilhado de normalização, configurável por engine.

Normalizar:

- números;
- ordinais;
- datas;
- horas;
- moedas;
- percentuais;
- unidades;
- siglas;
- abreviações;
- símbolos;
- URLs;
- e-mails;
- telefones;
- versões;
- intervalos;
- listas.

Exemplos:

- `R$ 1.250,30` → “mil duzentos e cinquenta reais e trinta centavos”;
- `8h30` → “oito e meia”;
- `NR-1` → “NR um”;
- `Dr. Paulo` → “doutor Paulo”;
- `15/03/2026` → “quinze de março de dois mil e vinte e seis”.

Preserve:

- texto original;
- texto normalizado;
- dicionário editável;
- regras por engine;
- opção de visualizar antes de gerar.

Não modifique permanentemente o texto do usuário.

Adicione testes com:

- ações;
- visualizações;
- psicologia;
- acolhimento;
- CIPA;
- NR-1;
- WhatsApp;
- YunoHost;
- Qwen;
- VibeVoice;
- datas;
- horas;
- valores em reais.

---

# 17. Renderização segmentada e montagem

Textos marcados ou longos devem ser segmentados.

Não enviar texto arbitrariamente longo em uma única inferência.

O segmentador deve respeitar:

- sentença;
- parágrafo;
- abreviações;
- números;
- citações;
- siglas;
- marcações;
- fronteiras semânticas.

Para cada segmento:

- salvar texto;
- texto normalizado;
- estilo;
- referência;
- engine;
- parâmetros;
- seed;
- status;
- áudio temporário;
- tempo;
- erro.

A montagem deve:

- preservar ordem;
- uniformizar taxa de amostragem;
- uniformizar canais;
- inserir pausas;
- inserir eventos;
- alinhar volume moderadamente;
- usar crossfade curto quando apropriado;
- evitar estalos;
- não cortar fonemas;
- evitar concatenação bruta;
- preservar respirações intencionais;
- permitir regenerar um segmento;
- permitir reproduzir um segmento;
- permitir cancelar tudo.

Não aplicar alteração agressiva de pitch.

Diferencie:

- velocidade nativa;
- velocidade por pós-processamento.

---

# 18. Integração do Chatterbox PT-BR

## 18.1. Modelo alvo

Use explicitamente:

`ResembleAI/Chatterbox-Multilingual-pt-br`

Não substitua silenciosamente por checkpoint multilíngue genérico.

Antes de implementar, confirme no upstream:

- nome correto;
- revisão;
- licença;
- arquivos;
- classe;
- API;
- dependências;
- parâmetros suportados;
- taxa de amostragem;
- requisitos de hardware.

## 18.2. Engine independente

Crie uma implementação separada, por exemplo:

```text
services/tts/chatterbox_ptbr_engine.py
```

Não colocar lógica Chatterbox dentro dos módulos VibeVoice.

Crie ou consolide:

```text
services/tts/
├── base.py
├── registry.py
├── dispatcher.py
├── schemas.py
├── normalizer_ptbr.py
├── orchestrator.py
├── audio_joiner.py
└── engines/
    ├── vibevoice_1_5b.py
    ├── vibevoice_realtime_0_5b.py
    ├── vibevoice_large.py
    └── chatterbox_ptbr.py
```

Adapte à arquitetura real do repositório. Não refatore sem necessidade.

## 18.3. Catálogo

Adicionar chave estável:

`chatterbox_pt_br`

Implementar:

- download;
- instalação;
- remoção;
- verificação;
- tamanho;
- status;
- carregamento;
- descarregamento;
- revisão;
- cache;
- erro.

Adicionar “Chatterbox PT-BR” ao seletor sem alterar o padrão atual.

## 18.4. Biblioteca compartilhada

Reutilizar o `reference.wav`.

Manter derivados separados:

```text
data/voices/<voice_id>/engines/chatterbox_pt_br/
```

Não usar embeddings do VibeVoice.

## 18.5. Parâmetros

Expor somente os suportados pela versão instalada, incluindo quando aplicável:

- `audio_prompt_path`;
- `exaggeration`;
- `cfg_weight`;
- `temperature`;
- `seed`;
- `top_p`;
- `min_p`;
- `repetition_penalty`.

Velocidade por pós-processamento deve ser identificada.

## 18.6. Capacidades

Na primeira versão, trate como:

- voz única;
- clonagem por referência;
- PT-BR;
- geração não streaming, salvo prova de suporte;
- sem multifalante nativo, salvo prova;
- estilos por referência e parâmetros.

Não finja recursos.

## 18.7. Hardware

Otimizar para:

- RTX 3050 6 GB;
- 32 GB RAM;
- Windows 11;
- ambiente atual do projeto.

Não aplicar automaticamente:

- quantização;
- `torch.compile`;
- aceleração experimental;
- troca de precisão.

Meça antes.

Modo CPU deve ser escolha explícita.

---

# 19. Interface

## 19.1. Modelos

Mostrar:

- VibeVoice 1.5B;
- VibeVoice Realtime 0.5B;
- VibeVoice Large;
- Chatterbox PT-BR.

Mostrar capacidades por engine.

## 19.2. Vozes

Permitir:

- criar;
- importar;
- ouvir;
- definir padrão;
- excluir;
- editar;
- gerar preview;
- visualizar compatibilidade.

## 19.3. Estilos

Na voz selecionada, mostrar:

- estilos iniciais opcionais;
- estilos do usuário;
- criar novo;
- duplicar;
- editar;
- gravar;
- importar;
- excluir;
- ordenar;
- habilitar;
- aliases;
- parâmetros;
- compatibilidade.

## 19.4. Editor

Adicionar:

- destaque de tags;
- autocomplete dinâmico;
- painel de parâmetros;
- validação;
- prévia do texto limpo;
- prévia da segmentação;
- linha do tempo;
- reprodução por segmento;
- regeneração;
- comparação de seed;
- indicação de incompatibilidade.

## 19.5. Transparência

Mostrar sempre:

- engine;
- modelo;
- revisão;
- dispositivo;
- voz;
- estilo;
- referência;
- parâmetros;
- status;
- tempo;
- erro.

Não indicar sucesso quando houve falha.

---

# 20. Segurança, privacidade e consentimento

Não enviar:

- gravações;
- embeddings;
- condicionamentos;
- estilos;
- eventos;
- áudio gerado;
- texto;
- metadados pessoais.

Permitir excluir completamente:

- voz;
- original;
- referência;
- estilos;
- eventos;
- previews;
- caches;
- derivados por engine.

Ao importar voz de terceiros, exigir confirmação de autorização.

---

# 21. Testes obrigatórios

## 21.1. VibeVoice

Testar:

- download;
- conversão;
- detecção;
- 1.5B CPU;
- 1.5B CUDA;
- ausência de fallback;
- voz personalizada;
- mudança de referência;
- cache;
- invalidação;
- multifalante;
- parâmetros;
- cancelamento;
- descarregamento;
- Realtime;
- WebSocket;
- voz portuguesa experimental;
- limitações de clonagem;
- Large em hardware insuficiente.

## 21.2. Biblioteca

Testar:

- primeira voz;
- instalação sem microfone;
- migração;
- gravação;
- upload;
- substituição;
- exclusão;
- voz padrão;
- exclusão da última voz;
- consentimento;
- persistência.

## 21.3. Estilos

Testar:

- estilos iniciais opcionais;
- excluir estilo inicial;
- criar estilo;
- duplicar;
- renomear;
- alias;
- referência;
- sem referência;
- compatibilidade;
- importação;
- exportação;
- estilo inexistente;
- colisão de tag.

## 21.4. Tags

Testar:

- tag simples;
- parâmetros;
- alias;
- tag personalizada;
- tag desconhecida;
- fechamento ausente;
- aninhamento proibido;
- valor fora de faixa;
- pausa;
- respiração;
- suspiro;
- risada;
- ausência de evento;
- tags nunca pronunciadas.

## 21.5. Áudio

Testar:

- segmentação;
- montagem;
- taxa de amostragem;
- canais;
- volume;
- crossfade;
- estalos;
- regeneração de segmento;
- cancelamento;
- temporários;
- texto longo.

## 21.6. Chatterbox

Testar:

- checkpoint PT-BR correto;
- catálogo;
- download;
- carregamento;
- voz;
- estilos;
- parâmetros;
- normalização;
- segmentação;
- CPU;
- CUDA;
- ausência de fallback;
- isolamento de dependências;
- regressão dos VibeVoice.

## 21.7. Regressão

Executar testes de:

- Whisper;
- VibeVoice ASR;
- frontend;
- backend;
- catálogo;
- instalador;
- gerenciamento de recursos;
- APIs internas;
- WebSocket.

---

# 22. Exemplos reais obrigatórios

No hardware disponível, gerar e salvar:

1. VibeVoice 1.5B com voz do usuário em PT-BR.
2. VibeVoice 1.5B com dois estilos.
3. VibeVoice 1.5B multifalante, se suportado.
4. Realtime 0.5B com voz portuguesa experimental.
5. Chatterbox PT-BR neutro.
6. Chatterbox PT-BR com voz clonada por upload.
7. Chatterbox PT-BR com voz gravada.
8. Chatterbox acolhedor.
9. Chatterbox sério.
10. Chatterbox com estilo criado pelo usuário.
11. Texto com tags, pausa e respiração.
12. Texto com números, datas, siglas e moeda.
13. Texto longo segmentado.
14. Comparação de duas seeds.
15. Regeneração de apenas um segmento.

Para cada exemplo, registrar:

- caminho do WAV;
- engine;
- checkpoint;
- dispositivo;
- voz;
- estilo;
- duração;
- tempo de carregamento;
- tempo até início;
- tempo total;
- fator de tempo real;
- RAM;
- VRAM;
- seed;
- parâmetros;
- observações.

Se o hardware não permitir um teste, declare explicitamente. Não simule validação.

---

# 23. Critérios de aceite

A implementação só pode ser considerada concluída quando:

- não existe SAPI5 no fluxo de produção;
- não existe senoide;
- não existe fallback automático;
- não existem vozes padrão distribuídas;
- a instalação solicita a primeira voz;
- sem voz, o TTS fica desabilitado;
- a voz gravada se torna padrão;
- estilos iniciais são opcionais;
- o usuário cria estilos próprios;
- tags são dinâmicas;
- tags nunca são pronunciadas;
- eventos são inseridos deterministicamente;
- Chatterbox é uma engine adicional;
- VibeVoice permanece disponível;
- o checkpoint PT-BR correto é carregado;
- o Realtime não promete clonagem;
- a voz portuguesa do Realtime não é chamada de PT-BR sem evidência;
- nenhuma engine simula recurso inexistente;
- cada áudio informa a engine real;
- cancelamento libera recursos;
- os modelos não contaminam dependências uns dos outros;
- os testes relevantes passam;
- exemplos reais são produzidos;
- regressões são verificadas.

---

# 24. Relatório final obrigatório

Ao terminar, apresente:

1. Resumo do que já existia.
2. Causas raiz encontradas.
3. Decisões arquiteturais.
4. Arquivos alterados.
5. Arquivos adicionados.
6. Dependências adicionadas ou alteradas.
7. Justificativa de cada versão pinada.
8. Comandos executados.
9. Testes executados.
10. Testes aprovados.
11. Testes falhos.
12. Testes não executados e motivo.
13. Modelos validados com áudio real.
14. Modelos não validados.
15. Caminhos dos WAVs.
16. Métricas de desempenho.
17. Limitações restantes.
18. Riscos conhecidos.
19. Próximos passos recomendados.
20. Revisão final do diff.

Não faça commit, push ou release.
