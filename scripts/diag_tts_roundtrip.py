"""Diagnóstico round-trip do VibeVoice TTS 1.5B em PT-BR.

Gate objetivo: gera frases curtas com o modelo REAL,
transcreve de volta com o Whisper large-v3-turbo e compara com a entrada.
Telemetria completa por tentativa (frames, EOS, motivo de parada, RMS...).

Condicionamento de voz (default ON): o port do fork define
``get_audio_features`` mas nunca a conecta ao generate — este script faz o
encaixe no nível de embeddings: as posições <|vision_pad|> da seção
"Voice input" recebem os embeddings acústicos da gravação de referência.

Uso:
  .venv\\Scripts\\python.exe scripts\\diag_tts_roundtrip.py [--no-voice] [--voice CAMINHO.wav] [--cap N]
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import scipy.io.wavfile as wavfile

# Console do Windows usa cp1252; transcrições podem trazer qualquer Unicode.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()
import torch

from services.transformers_loader import apply_vibevoice_fork_patches, use_custom_transformers

CONVERTED_DIR = PROJECT_ROOT / "models" / "VibeVoice-1.5B-hf"
OUT_DIR = PROJECT_ROOT / "temp_uploads" / "tts_diag"
DEFAULT_VOICE = PROJECT_ROOT / "temp_uploads" / "retained"
SAMPLE_RATE = 24000
HOP = 3200  # amostras por frame acústico (24kHz / 7.5Hz)

PHRASES = [
    ("teste1", "Olá, mundo."),
    ("teste2", "Bom dia."),
    ("teste3", "Teste de voz."),
    ("teste4", "Speaker 1: Olá, mundo."),
]

SYSTEM_PROMPT = (" Transform the text provided by various speakers into speech output, "
                 "utilizing the distinct voice of each respective speaker.\n")


def find_default_voice() -> Path | None:
    if DEFAULT_VOICE.is_dir():
        candidates = sorted(DEFAULT_VOICE.glob("*.*"), key=lambda p: p.stat().st_size, reverse=True)
        for path in candidates:
            if path.stat().st_size > 20_000:
                return path
    return None


def build_prompt(phrase: str, n_voice_pads: int = 0, speaker: str = "1") -> str:
    """Replica o chat_template.jinja do checkpoint convertido."""
    match = re.match(r"speaker\s*(\d+)\s*:\s*(.*)", phrase, re.IGNORECASE)
    if match:
        speaker, phrase = match.group(1), match.group(2)
    voice_section = ""
    if n_voice_pads > 0:
        voice_section = (
            " Voice input:\n"
            + f" Speaker {speaker}:<|vision_start|>" + "<|vision_pad|>" * n_voice_pads + "<|vision_end|>\n"
        )
    return (
        SYSTEM_PROMPT
        + voice_section
        + " Text input:\n"
        + f" Speaker {speaker}: {phrase}\n"
        + " Speech output:\n"
        + "<|vision_start|>"
    )


def normalize(text: str, strip_accents: bool = False) -> str:
    text = text.lower().strip()
    if strip_accents:
        text = "".join(c for c in unicodedata.normalize("NFD", text)
                       if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\sáéíóúâêôãõçà]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_voice_reference(path: Path, start_seconds: float, max_seconds: float) -> np.ndarray:
    from services.transcriber import decode_audio_ffmpeg

    audio = decode_audio_ffmpeg(str(path), sampling_rate=SAMPLE_RATE)
    start = int(start_seconds * SAMPLE_RATE)
    audio = audio[start:start + int(max_seconds * SAMPLE_RATE)]
    return audio.astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, default=512)
    parser.add_argument("--no-voice", action="store_true", help="desliga o condicionamento de voz (modo H1)")
    parser.add_argument("--voice", type=str, default=None, help="arquivo de áudio de referência (PT-BR)")
    parser.add_argument("--voice-start", type=float, default=0.3, help="início do recorte da referência (s)")
    parser.add_argument("--voice-len", type=float, default=6.0, help="duração do recorte da referência (s)")
    parser.add_argument("--cfg", type=float, default=None, help="cfg_scale (default do checkpoint: 1.3)")
    parser.add_argument("--steps", type=int, default=None, help="n_diffusion_steps (default do checkpoint: 10)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assert CONVERTED_DIR.is_dir(), "rode scripts/convert_vibevoice_1_5b.py antes"

    voice_audio = None
    voice_label = "(sem condicionamento)"
    if not args.no_voice:
        if args.voice:
            voice_path = Path(args.voice)
            voice_audio = load_voice_reference(voice_path, args.voice_start, args.voice_len)
            voice_label = f"{voice_path} (recorte {args.voice_start:.1f}s+{len(voice_audio)/SAMPLE_RATE:.1f}s)"
        else:
            voice_path = find_default_voice()
            if voice_path is None:
                print("AVISO: nenhuma gravação de referência encontrada; rodando sem condicionamento.")
            else:
                voice_audio = load_voice_reference(voice_path, args.voice_start, args.voice_len)
                voice_label = f"{voice_path} (recorte {args.voice_start:.1f}s+{len(voice_audio)/SAMPLE_RATE:.1f}s)"
    if voice_audio is not None:
        print(f"voz de referência: {voice_label} ({len(voice_audio)/SAMPLE_RATE:.1f}s)")
        ref_wav = OUT_DIR / "referencia_voz.wav"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        wavfile.write(str(ref_wav), SAMPLE_RATE, (np.clip(voice_audio, -1, 1) * 32767).astype(np.int16))

    results = []

    with use_custom_transformers():
        apply_vibevoice_fork_patches()
        from transformers import AutoModelForTextToWaveform, AutoProcessor

        processor = AutoProcessor.from_pretrained(str(CONVERTED_DIR))
        print(f"processor: {type(processor).__name__} | tokenizer: {type(processor.tokenizer).__name__}")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = AutoModelForTextToWaveform.from_pretrained(
            str(CONVERTED_DIR), dtype=torch.bfloat16,
        ).to(device).eval()
        gen_cfg = model.generation_config
        print(f"modelo: {type(model).__name__} | device: {device} | "
              f"eos={gen_cfg.eos_token_id} speech_end={getattr(gen_cfg, 'speech_end_id', None)} "
              f"cfg_scale={getattr(gen_cfg, 'cfg_scale', None)}")
        speech_end_id = int(getattr(gen_cfg, "speech_end_id", 151653) or 151653)
        diffusion_id = int(model.config.speech_diffusion_id)

        import copy
        run_gen_cfg = copy.deepcopy(gen_cfg)
        if args.cfg is not None:
            run_gen_cfg.cfg_scale = args.cfg
        if args.steps is not None:
            run_gen_cfg.n_diffusion_steps = args.steps
        print(f"parâmetros desta rodada: cfg_scale={run_gen_cfg.cfg_scale} "
              f"n_diffusion_steps={getattr(run_gen_cfg, 'n_diffusion_steps', None)}")

        # ---- embeddings da voz de referência (uma vez)
        voice_embeds = None
        if voice_audio is not None:
            fe_out = processor.feature_extractor(
                voice_audio, sampling_rate=SAMPLE_RATE, return_tensors="pt",
                padding=True, pad_to_multiple_of=HOP,
            )
            print("feature_extractor keys:", {k: tuple(v.shape) for k, v in fe_out.items() if hasattr(v, 'shape')})
            feats = fe_out["input_features"].to(device=device, dtype=torch.bfloat16)
            if feats.dim() == 2:           # (B, T) -> (B, 1, T) se o encoder pedir canal
                try_input = feats
            else:
                try_input = feats
            n_frames = int(try_input.shape[-1] // HOP)
            mask = torch.ones((1, n_frames), dtype=torch.bool, device=device)
            with torch.no_grad():
                try:
                    voice_embeds = model.get_audio_features(try_input, mask)
                except Exception:
                    voice_embeds = model.get_audio_features(try_input.unsqueeze(1), mask)
            print(f"voice_embeds: shape {tuple(voice_embeds.shape)} dtype {voice_embeds.dtype} "
                  f"| frames de voz: {n_frames} | NaN {bool(torch.isnan(voice_embeds).any())}")

        for name, phrase in PHRASES:
            n_pads = int(voice_embeds.shape[0]) if voice_embeds is not None else 0
            prompt = build_prompt(phrase, n_voice_pads=n_pads)
            print(f"\n===== {name}: {phrase!r} (voice_pads={n_pads}) =====")

            inputs = processor(text=prompt)
            input_ids = inputs["input_ids"].to(device)
            attention_mask = inputs["attention_mask"].to(device)
            prompt_len = int(input_ids.shape[1])
            print(f"input_ids: {tuple(input_ids.shape)} int64")

            generate_kwargs = dict(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=args.cap,
                return_dict_in_generate=True,
                generation_config=run_gen_cfg,
            )
            if voice_embeds is not None:
                embed_layer = model.get_input_embeddings()
                inputs_embeds = embed_layer(input_ids).clone()
                pad_positions = input_ids == diffusion_id
                n_positions = int(pad_positions.sum().item())
                assert n_positions == voice_embeds.shape[0], (n_positions, voice_embeds.shape)
                inputs_embeds[pad_positions] = voice_embeds.to(inputs_embeds.dtype)
                generate_kwargs["inputs_embeds"] = inputs_embeds

            started = time.time()
            with torch.no_grad():
                output = model.generate(**generate_kwargs)
            gen_seconds = time.time() - started

            sequences = getattr(output, "sequences", None)
            new_tokens = sequences[0][prompt_len:].tolist() if sequences is not None and sequences.shape[1] >= prompt_len else (sequences[0].tolist() if sequences is not None else [])
            has_speech_end = speech_end_id in new_tokens
            reach_max = getattr(output, "reach_max_step_sample", None)
            reach_max_value = bool(reach_max[0].item()) if reach_max is not None else None

            audio_list = getattr(output, "audio", None)
            if not audio_list:
                print("SEM ÁUDIO no output!")
                continue
            audio = audio_list[0].detach().to(torch.float32).cpu().numpy().squeeze()

            duration = len(audio) / SAMPLE_RATE
            frames = len(audio) // HOP
            rms = float(np.sqrt((audio ** 2).mean()))
            peak = float(np.abs(audio).max())
            stop_reason = "cap/max_steps" if reach_max_value else (
                "speech_end (EOS de fala)" if has_speech_end else "outro")

            wav_path = OUT_DIR / f"{name}.wav"
            wavfile.write(str(wav_path), SAMPLE_RATE, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
            print(f"duração {duration:.2f}s | frames {frames} | rms {rms:.4f} | pico {peak:.3f} | "
                  f"EOS fala: {has_speech_end} | motivo: {stop_reason} | geração {gen_seconds:.1f}s")

            results.append({"name": name, "phrase": phrase, "duration": duration, "frames": frames,
                            "speech_end": has_speech_end, "stop_reason": stop_reason, "wav": str(wav_path)})

    print("\ncarregando whisper large-v3-turbo (cpu/int8) para o round-trip...")
    from faster_whisper import WhisperModel
    from services.model_manager import get_whisper_cache_dir

    whisper = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8",
                           download_root=str(get_whisper_cache_dir()))

    if voice_audio is not None:
        ref_segments, ref_info = whisper.transcribe(str(OUT_DIR / "referencia_voz.wav"),
                                                    beam_size=5, vad_filter=True, language="pt")
        ref_text = " ".join(s.text.strip() for s in ref_segments).strip()
        print(f"\nconteúdo da REFERÊNCIA de voz (controle de vazamento): {ref_text!r}")

    print("\n| Entrada PT-BR | Duração | Frames | EOS | Whisper (auto) | Idioma | Whisper (pt forçado) | Resultado |")
    print("|---|---:|---:|---|---|---|---|---|")
    for entry in results:
        segments, info = whisper.transcribe(entry["wav"], beam_size=5, vad_filter=True)
        text_auto = " ".join(s.text.strip() for s in segments).strip()
        lang = f"{info.language} ({info.language_probability:.2f})"
        segments_pt, _ = whisper.transcribe(entry["wav"], beam_size=5, vad_filter=True, language="pt")
        text_pt = " ".join(s.text.strip() for s in segments_pt).strip()

        expected = re.sub(r"(?i)^speaker\s*\d+\s*:\s*", "", entry["phrase"])
        words_in = set(normalize(expected, True).split())

        def recovered_in(text):
            return len(words_in & set(normalize(text, True).split()))

        rec_auto, rec_pt = recovered_in(text_auto), recovered_in(text_pt)
        best = max(rec_auto, rec_pt)
        if len(words_in) and best == len(words_in):
            verdict = "FUNCIONAL"
        elif best >= max(1, len(words_in) - 1):
            verdict = "FUNCIONAL" if best >= 2 else "PARCIAL"
        elif best >= 1:
            verdict = "PARCIAL"
        else:
            verdict = "NÃO FUNCIONAL"

        print(f"| {entry['phrase']} | {entry['duration']:.1f}s | {entry['frames']} | "
              f"{'sim' if entry['speech_end'] else 'NÃO'} | {text_auto or '(vazio)'} | {lang} | "
              f"{text_pt or '(vazio)'} | {verdict} |")

    print("\nDIAG CONCLUÍDO")


if __name__ == "__main__":
    main()
