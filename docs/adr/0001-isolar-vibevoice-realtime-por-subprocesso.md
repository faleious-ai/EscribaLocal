# Isolar VibeVoice Realtime por subprocesso

Status: accepted

O VibeVoice Realtime 0.5B continua indisponível no processo principal até existir uma prova de geração nativa real. Quando o suporte for retomado, ele deve entrar por um ambiente isolado/subprocesso, não por upgrade direto do `transformers` nem por adapter carregado dentro do runtime principal, porque o EscribaLocal já alterna entre `transformers` padrão e um fork vendored para VibeVoice 1.5B/ASR, e misturar mais uma pilha de dependências no mesmo processo aumenta o risco de quebrar TTS 1.5B, ASR e futuros adapters.

## Considered Options

- Adapter nativo no processo atual: rejeitado por risco de conflito com `custom_transformers`, `huggingface_hub` vendored e patches de compatibilidade do VibeVoice 1.5B.
- Upgrade controlado de dependências no processo principal: rejeitado por alto risco de regressão cruzada e difícil rollback.
- Ambiente isolado/subprocesso: aceito por isolar versões, crashes, logs e testes de áudio nativo sem contaminar o runtime principal.
- Manter indisponível sem próxima ação: rejeitado porque a UI e o catálogo já preservam o modelo como possibilidade futura.

## Consequences

- Realtime 0.5B só pode ser anunciado como disponível depois de um subprocesso retornar áudio PCM/WAV nativo, sem SAPI5, tom sintético ou fallback de outra engine.
- O aceite mínimo exige registrar `engine_key=realtime_0_5b`, versão/ambiente do worker, amostra audível, latência inicial, chunks reais e erro estruturado quando o worker não estiver pronto.
- Clonagem por `reference.wav`, multi-speaker e suporte PT-BR não são assumidos para o Realtime 0.5B; qualquer suporte precisa ser provado por teste separado antes de aparecer na UI.
- O caminho do VibeVoice 1.5B e Chatterbox deve permanecer independente do worker Realtime.
