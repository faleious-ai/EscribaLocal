# Continuidade Codex — ajuste do Gate A e preparação para revisão externa

**Projeto:** EscribaLocal  
**Repositório:** `faleious-ai/EscribaLocal`  
**Branch de trabalho esperada:** `codex/tts-gate-a`  
**PR relacionado:** `#15 — [codex] Gate A TTS remove forbidden fallbacks`  
**Objetivo desta rodada:** corrigir as pendências da auditoria revisada, deixar o Gate A internamente consistente e preparar evidências suficientes para uma revisão externa posterior.

---

# 1. Regra de trabalho

Você já implementou as etapas anteriores deste projeto. Continue a partir do estado atual da branch de trabalho.

Não recomece o projeto.  
Não reescreva a aplicação.  
Não repita tarefas já concluídas sem antes verificar o código.  
Não use a PRD histórica como limite do escopo atual.

Antes de qualquer alteração:

1. confirme que está na branch `codex/tts-gate-a`;
2. execute `git status`;
3. preserve todo trabalho existente;
4. compare a branch com `main`;
5. leia integralmente os arquivos listados na seção seguinte;
6. confirme no código cada achado da auditoria antes de corrigi-lo.

Não confie cegamente em nenhum relatório. A fonte final é o código atual da branch.

---

# 2. Arquivos obrigatórios

Leia nesta ordem:

1. `AGENTS.md`;
2. `CONTEXT.md`;
3. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`;
4. `docs/tts/gate-a-baseline.md`;
5. `docs/tts/gate-a-report.md`;
6. `AUDITORIA_PLANO_IMPLEMENTACAO_TTS_ESCRIBALOCAL_V2_BRANCH.md`, quando estiver anexado ou copiado para o repositório;
7. ADRs relevantes em `docs/adr/`;
8. documentação operacional em `docs/agents/`.

Precedência em caso de conflito:

1. instrução explícita mais recente do usuário;
2. `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`;
3. este documento;
4. auditoria revisada;
5. ADRs compatíveis;
6. `AGENTS.md`;
7. PRD e issues históricas;
8. comportamento legado.

---

# 3. Limite desta rodada

Esta rodada deve:

- finalizar o Gate A;
- corrigir as ressalvas da auditoria;
- melhorar a governança de execução;
- reforçar os testes;
- deixar o próximo gate claramente preparado.

Esta rodada não deve implementar:

- estilos persistentes;
- eventos vocais;
- tags diretas;
- novo parser;
- AST;
- RenderPlan;
- AudioAssembler;
- timeline;
- falantes virtuais;
- job pai de renderização;
- Render API;
- Realtime nativo;
- UI completa de estilos;
- funcionalidades dos Gates B, C, D, E, F ou G.

Não “adiantar” funcionalidades futuras.

---

# 4. Estado esperado antes das correções

A branch já deve conter, no mínimo:

- escopo versionado em `docs/tts/`;
- `CONTEXT.md`;
- remoção de presets Windows como vozes resolvíveis;
- remoção de SAPI5 e senoide do runtime;
- Large bloqueado sem referências reais;
- synthetic smoke removido;
- proteção contra engine diferente da solicitada;
- testes negativos;
- relatório do Gate A.

Se algum desses itens não estiver presente, diagnostique a divergência antes de prosseguir.

---

# 5. Correções obrigatórias

# 5.1. Migração de configurações legadas

Localize todas as formas pelas quais uma instalação antiga pode preservar:

- `preset_windows_1`;
- `preset_windows_2`;
- `preset_windows_3`;
- `preset_windows_4`;
- `speaker_1`;
- `speaker_2`;
- `speaker_3`;
- `speaker_4`;
- aliases antigos usados como identidade vocal;
- valores persistidos em configuração;
- valores persistidos em `localStorage`;
- mapas antigos de falantes;
- seleção antiga de voz padrão;
- estado de setup que considere voz Windows válida.

Implemente migração idempotente.

Comportamento obrigatório:

- não apagar vozes reais;
- não converter silenciosamente um ID legado em outra identidade;
- usar uma voz real padrão somente quando já existir uma única escolha inequívoca;
- caso contrário, limpar a seleção;
- manter o TTS como pendente ou desabilitado;
- orientar o usuário a criar ou selecionar uma voz real;
- nunca recriar preset Windows;
- nunca retornar SAPI5 ou senoide;
- executar a migração apenas quando necessário;
- permitir rodar a migração mais de uma vez sem efeito colateral.

Cobertura mínima:

- configuração contendo `preset_windows_1`;
- configuração contendo `speaker_1`;
- configuração com voz real válida;
- configuração sem voz;
- configuração com ID inexistente;
- `localStorage` antigo;
- primeira execução após atualização;
- segunda execução após migração.

---

# 5.2. Ledger de execução

Crie:

```text
docs/tts/EXECUTION_STATUS.md
```

Esse arquivo deve ser a fonte de verdade do progresso de implementação.

Campos mínimos por tarefa:

- ID;
- nome;
- gate;
- estado;
- branch;
- PR;
- commit;
- evidência;
- testes;
- pendências;
- dependências;
- próximo passo permitido.

Estados válidos:

- `not_started`;
- `in_progress`;
- `implemented`;
- `verified`;
- `blocked`;
- `superseded`.

Não marque uma tarefa como `verified` apenas porque existe código. Exija evidência de teste ou revisão.

Registre o Gate A com o estado real de cada tarefa:

- T0.1;
- T0.2;
- T1.1;
- T1.2;
- T1.3;
- T9.3;
- T10.1.

Se uma tarefa possuir ressalva, não a marque como totalmente verificada.

Atualize `CONTEXT.md` para exigir a leitura conjunta de:

1. escopo;
2. ledger de execução;
3. relatório do gate atual.

Não transforme o escopo em diário de execução.

---

# 5.3. Compatibilidade `is_preset`

Localize todos os callers de:

```python
is_preset(...)
```

Escolha uma estratégia explícita:

## Estratégia preferida

- remover todos os callers;
- apagar a função;
- substituir verificações necessárias por conceitos atuais:
  - voz real válida;
  - ID legado proibido;
  - voz inexistente.

## Estratégia temporária permitida

Manter a função somente quando a remoção imediata quebrar compatibilidade comprovada.

Nesse caso:

- marcar como deprecated;
- documentar os únicos callers permitidos;
- adicionar teste que falhe se novos callers aparecerem;
- criar uma tarefa explícita de remoção no ledger;
- não usá-la em código novo.

Não manter indefinidamente uma função que sempre retorna `False`.

---

# 5.4. Robustez do teste de caminhos proibidos

Atualize:

```text
tests/test_tts_forbidden_runtime_paths.py
```

Não dependa do diretório atual de execução.

Use a raiz calculada a partir do próprio arquivo:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

O teste deve funcionar quando executado:

- na raiz;
- em outro diretório;
- isoladamente;
- dentro da suíte completa.

Mantenha a distinção entre:

- código funcional proibido;
- documentação que descreve proibições;
- mensagens de erro que citam SAPI5 ou senoide;
- testes negativos que simulam valores proibidos.

O teste não deve falhar por documentação histórica legítima.

---

# 5.5. Matriz de mismatch de engine

Amplie os testes do endpoint ou serviço central.

Cobrir separadamente:

| Engine solicitada | Engine executada | fallback | Resultado |
|---|---|---:|---|
| `tts_1_5b` | `tts_1_5b` | `false` | permitido |
| `tts_1_5b` | `chatterbox-tts-pt-br` | `false` | rejeitado |
| `chatterbox-tts-pt-br` | `tts_1_5b` | `false` | rejeitado |
| `tts_1_5b` | `tts_1_5b` | `true` | rejeitado |
| `chatterbox-tts-pt-br` | `chatterbox-tts-pt-br` | `true` | rejeitado |
| engine solicitada válida | engine ausente nos metadados | — | política explícita |

Defina a política para engine ausente nos metadados.

Recomendação:

- sucesso de produção deve exigir `engine_key` explícita;
- não assumir a engine solicitada quando o adapter omitir metadados;
- adapters legados devem ser corrigidos.

Teste a validação preferencialmente em uma função pura reutilizável, não apenas dentro da rota.

---

# 5.6. Atualização do relatório do Gate A

Atualize:

```text
docs/tts/gate-a-report.md
```

O relatório deve separar:

- implementado;
- validado;
- não validado;
- bloqueado;
- movido explicitamente para Gate B.

Incluir:

- commit-base;
- commit final;
- branch;
- PR;
- arquivos alterados;
- testes executados;
- resultado;
- ambiente;
- comandos;
- migração legada;
- limitações;
- dívidas deliberadas;
- próximo gate permitido.

Não declarar o Gate A totalmente concluído antes de cumprir os critérios da seção 8.

---

# 5.7. Tracker histórico

Não altere issues remotas sem autorização explícita.

Prepare em:

```text
docs/tts/TRACKER_UPDATE_PROPOSAL.md
```

dois textos:

1. comentário recomendado para a issue-mãe histórica;
2. corpo recomendado para uma nova issue-mãe do escopo atual.

O texto deve esclarecer:

- a PRD antiga é histórica;
- o Gate A foi executado no PR #15;
- o escopo atual inclui novos gates;
- issues antigas não representam conclusão do produto atual;
- QA antigo não encerra o novo escopo.

Não publicar esses textos.

---

# 6. Revisão técnica obrigatória

Antes de concluir, revise especificamente:

## Biblioteca de vozes

- nenhum preset Windows é listado;
- aliases antigos não resolvem voz;
- uma voz real continua válida;
- exclusão e default funcionam;
- migração não apaga dados;
- ausência de voz produz estado correto.

## VibeVoice 1.5B

- não há SAPI5;
- não há senoide;
- não há voz substituta;
- embeddings continuam usando referência real;
- cache continua invalidado por hash e revisão;
- erro de voz continua explícito.

## VibeVoice Large

- permanece bloqueado;
- não carrega sem referências reais;
- não cria referência artificial;
- erro permanece acionável.

## Realtime

- não existe synthetic smoke;
- cliente rejeita resposta sintética antiga;
- worker retorna erro estruturado;
- UI continua sem prometer áudio real.

## Chatterbox

- não virou fallback;
- não recebe voz Windows;
- engine real é informada;
- mismatch é rejeitado.

## Endpoint

- engine solicitada deve coincidir com a executada;
- fallback verdadeiro é rejeitado;
- voz legada é rejeitada;
- erros não retornam WAV.

---

# 7. Validação obrigatória

Execute e registre os comandos exatos.

Mínimo:

```text
python -m pytest
python -m pytest tests/test_tts_forbidden_runtime_paths.py
python -m pytest tests/test_tts_no_fallbacks.py
python -m pytest tests/test_tts_realtime_worker.py
python -m pytest tests/test_tts_large_clear_errors.py
python -m pytest tests/test_voice_profiles.py
```

Também executar:

- busca estática de caminhos proibidos;
- `git diff --check`;
- revisão do diff;
- teste de sintaxe/importação;
- teste de migração em diretório temporário;
- teste da suíte iniciado fora da raiz, quando aplicável.

Busca mínima:

```text
SAPI
win32com
pyttsx3
System.Speech
SpVoice
preset_windows
PRESET_VOICES
math.sin
np.sin
synthetic_smoke
fallback
speaker_1
speaker_2
speaker_3
speaker_4
```

Classifique cada ocorrência como:

- funcional proibida;
- compatibilidade rejeitora;
- documentação;
- teste negativo;
- falso positivo.

Não remova mensagens de erro só para fazer a busca ficar vazia.

---

# 8. Critérios de conclusão do Gate A

O Gate A está pronto para revisão externa somente quando:

- [ ] escopo está versionado;
- [ ] `CONTEXT.md` aponta para escopo, ledger e relatório;
- [ ] ledger registra progresso real;
- [ ] configurações legadas são migradas de forma idempotente;
- [ ] presets Windows não são vozes;
- [ ] aliases antigos não resolvem voz;
- [ ] SAPI5 não existe como caminho funcional;
- [ ] senoide não existe como caminho funcional;
- [ ] synthetic smoke não existe;
- [ ] Large não fabrica referência;
- [ ] engine diferente é rejeitada;
- [ ] `fallback=true` é rejeitado;
- [ ] engine ausente possui política explícita;
- [ ] `is_preset` foi removido ou deprecado de forma controlada;
- [ ] teste estático independe do CWD;
- [ ] suíte completa passa;
- [ ] testes direcionados passam;
- [ ] diff foi revisado;
- [ ] relatório foi atualizado;
- [ ] proposta de atualização do tracker foi criada;
- [ ] nenhum item de Gate B foi implementado.

---

# 9. Pacote de revisão externa

Ao concluir, crie:

```text
docs/tts/gate-a-review-package.md
```

Esse arquivo deve permitir que um revisor independente audite o trabalho sem reconstruir toda a história.

Estrutura obrigatória:

## 1. Resumo

- objetivo;
- branch;
- base;
- head;
- PR;
- escopo executado.

## 2. Decisões

- decisões tomadas;
- alternativas rejeitadas;
- dívidas deliberadas.

## 3. Arquivos alterados

Tabela:

| Arquivo | Alteração | Motivo | Risco |
|---|---|---|---|

## 4. Migração

- dados antigos reconhecidos;
- regra de migração;
- idempotência;
- rollback;
- testes.

## 5. Testes

Tabela:

| Comando | Resultado | Observações |
|---|---|---|

## 6. Evidências

- busca estática;
- testes negativos;
- exemplos de erro;
- comportamento sem voz;
- comportamento com ID legado;
- comportamento de mismatch.

## 7. Itens não executados

- o que não foi testado;
- por quê;
- risco remanescente.

## 8. Pendências do Gate B

Listar apenas, sem implementar:

- schema de voz v2;
- registry lazy;
- capability matrix;
- contratos de render;
- jobs compostos;
- estilos;
- parser;
- assembler;
- UI.

## 9. Diff final

- resumo;
- arquivos inesperados;
- alterações fora do escopo;
- confirmação de que não houve commit/push adicional não solicitado.

---

# 10. Resposta final ao usuário

Ao terminar, responda em português brasileiro com:

1. resumo objetivo;
2. branch e commit trabalhados;
3. arquivos alterados;
4. migração implementada;
5. testes executados;
6. resultados;
7. limitações;
8. arquivos de revisão gerados;
9. pontos que o revisor deve verificar;
10. confirmação de que o Gate B não foi iniciado.

Não diga apenas “concluído”.

---

# 11. Restrições finais

- não fazer merge;
- não fechar o PR;
- não publicar comentário;
- não alterar issues;
- não fazer push sem autorização;
- não apagar vozes reais;
- não alterar ASR;
- não atualizar dependências sem justificativa;
- não implementar Gates B em diante;
- não esconder teste falho;
- não declarar validação de áudio real sem ter gerado e ouvido;
- não considerar relatório anterior como prova suficiente;
- não modificar este documento para reduzir os critérios.

---

# 12. Comando de início

Use esta instrução operacional:

> Leia integralmente os arquivos obrigatórios, audite o estado atual da branch `codex/tts-gate-a`, implemente somente as correções deste documento, execute todos os testes e gere `docs/tts/gate-a-review-package.md`. Pare ao final do Gate A e aguarde revisão externa.
