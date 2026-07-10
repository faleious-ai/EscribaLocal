# Gramática formal do roteiro TTS

Status: contrato de T4.1 para a implementação do parser/AST em T4.2.

## Regras semânticas

* Tags e subtítulos nunca são enviados como texto falado à engine.
* O nome de um estilo é resolvido posteriormente na biblioteca da voz; a
  gramática aceita nomes e aliases, mas não valida sua existência.
* `falante` identifica um speaker lógico, não uma voz ou engine diretamente.
* A sintaxe provisória `[style:calmo]` permanece compatível apenas até T4.2; a
  sintaxe canônica abaixo é a única que novos roteiros devem produzir.

## EBNF

```ebnf
roteiro          = { item } ;
item             = subtitulo | bloco_estilo | pausa | evento | texto ;

subtitulo        = "##", espacos, conteudo_linha, quebra_linha ;
bloco_estilo     = abertura_estilo, { item }, fechamento_estilo ;
abertura_estilo  = "[", nome_estilo, { espacos, parametro }, "]" ;
fechamento_estilo= "[/", nome_estilo, "]" ;
parametro        = nome_parametro, "=", valor ;
pausa            = "[pausa", espacos, duracao, "]" ;
evento           = "[", nome_evento, [ espacos, modificador_evento ], "]" ;

nome_estilo      = identificador ;
nome_evento      = "respiracao" | "suspiro" | "risada" ;
nome_parametro   = identificador ;
valor            = identificador | numero | texto_entre_aspas ;
duracao          = numero, ( "ms" | "s" ) ;
identificador    = letra, { letra | digito | "_" | "-" } ;
numero           = digito, { digito }, [ ".", digito, { digito } ] ;
```

Parâmetros canônicos iniciais: `falante`, `intensidade` e `ritmo`. Outros
parâmetros nomeados são sintaticamente válidos e serão validados pela capability
matrix posterior.

## Exemplos

Válido:

```text
## Introdução
[calmo falante=ana intensidade=0.7]
Olá, esta é uma explicação pausada.
[/calmo]
[pausa 400ms]
[respiracao profunda]
```

Inválido:

```text
[calmo falante=ana]
Texto sem fechamento.

[pausa rápido]
```

O parser de T4.2 deve informar a posição do erro para fechamento ausente,
duração inválida e delimitadores malformados.
