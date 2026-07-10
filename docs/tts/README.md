# TTS — mapa de documentação e recuperação

Este diretório concentra a especificação, o estado operacional e as evidências do subsistema TTS. Nem todo arquivo deve ser carregado em toda sessão.

## Carregar sempre para retomar TTS

1. `CONTEXT.md`
2. `docs/tts/CURRENT_RUNWAY.md`

## Carregar para especificação

- `docs/tts/ESCOPO_DECISOES_PLANO_TTS_ESCRIBALOCAL.md`
- `docs/tts/RENDERPLAN_CONTRACT.md` quando a frente ativa envolver T4.x/T5.x
- ADRs relevantes em `docs/adr/`

## Carregar para execução

- issue ativa no GitHub;
- `docs/tts/ISSUE_EXECUTION_PLAN.md` quando houver fila, dependências ou múltiplas frentes;
- `docs/tts/EXECUTION_STATUS.md` quando for necessário consultar evidências ou histórico detalhado.

## Carregar para evidência histórica

- relatório do gate aplicável;
- comentários de fechamento das issues;
- commits e testes registrados no ledger.

## Não carregar por padrão

- drafts de issues antigas;
- propostas de atualização do tracker já executadas;
- PRDs históricas;
- relatórios de gates encerrados sem relação com a tarefa ativa;
- o repositório inteiro.

## Classificação dos documentos

| Classe | Função | Exemplos |
| --- | --- | --- |
| `canonical` | decisão, contrato e invariante | escopo consolidado, ADRs, `RENDERPLAN_CONTRACT.md` |
| `operational` | cursor, fila e estado mutável | `CURRENT_RUNWAY.md`, `ISSUE_EXECUTION_PLAN.md`, `EXECUTION_STATUS.md` |
| `evidence` | prova de execução ou gate | relatórios, comentários, commits e resultados de testes |
| `historical` | contexto de origem | PRDs e planos antigos |
| `superseded` | não deve governar execução | drafts e propostas substituídas pelo tracker real |

## Regra de precedência

1. decisão explícita mais recente do usuário;
2. especificações canônicas;
3. issue ativa delimitada;
4. ledger e runway;
5. ADRs compatíveis;
6. documentos operacionais de agentes;
7. materiais históricos.

Se dois arquivos operacionais divergirem, corrija o mais antigo. Não use a divergência como motivo para reinterpretar o escopo.