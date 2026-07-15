# Contrato do AudioAssembler — T7.1

Status: normativo para a issue #32.

## Decisão de saída

- WAV PCM signed 16-bit, mono, 24.000 Hz;
- segmentos entram na ordem de `RenderJob.order`;
- `pause_before_ms` é inserido imediatamente antes do segmento;
- eventos declarados em `events_before` entram na mesma posição, na ordem declarada;
- a ausência do áudio de um evento referenciado falha explicitamente;
- cada segmento recebe fades de borda de 5 ms para evitar descontinuidades;
- crossfade de estilo e regeneração individual ficam fora de T7.1.

## Interface pública

`assemble_render_plan(plan, segments, events=None)` recebe um `RenderPlan`, um mapa
`job_id -> áudio` e opcionalmente um mapa `event_id -> áudio`. O áudio pode ser
`bytes` WAV ou `numpy.ndarray` mono/estéreo. Retorna bytes WAV e um manifesto
serializável com `sample_rate`, `channels`, `duration_ms` e os itens da timeline.

As entradas são convertidas para a saída canônica sem mutar buffers do chamador.
O manifesto mantém a identidade dos jobs e registra a duração final.
