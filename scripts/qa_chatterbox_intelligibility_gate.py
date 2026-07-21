"""Gate de inteligibilidade do Chatterbox PT-BR.

Regra (definida pelo usuario): se o melhor modelo de transcricao (Whisper
large-v3) nao consegue entender a fala gerada, a engine nao esta madura nem
para ajuste fino. O minimo aceitavel e ser inteligivel.

Para cada amostra do manifesto mais recente, transcreve o WAV com o Whisper
large-v3 e mede a recuperacao de palavras de conteudo em relacao ao texto de
entrada. Grava a transcricao e o veredito de volta no manifesto.

Uso:
  .venv\\Scripts\\python.exe scripts\\qa_chatterbox_intelligibility_gate.py [--dir DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Palavras funcionais curtas que nao contam para inteligibilidade de conteudo.
STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "em", "no", "na", "um", "uma", "que",
    "ou", "os", "as", "ao", "com", "por", "se", "sua", "seu", "e",
}


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_words(text: str) -> set[str]:
    return {w for w in normalize(text).split() if len(w) > 2 and w not in STOPWORDS}


def find_latest_manifest() -> Path:
    base = PROJECT_ROOT / "data" / "tts_qa"
    manifests = sorted(base.glob("chatterbox-*/manifest.json"))
    if not manifests:
        raise SystemExit("Nenhum manifesto encontrado; rode qa_chatterbox_pt_br.py antes.")
    return manifests[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, help="Diretorio da execucao (default: mais recente).")
    parser.add_argument("--model", default="large-v3", help="Modelo faster-whisper (default: large-v3).")
    parser.add_argument("--pass-threshold", type=float, default=0.8,
                        help="Fracao minima de palavras de conteudo recuperadas para PASSAR.")
    args = parser.parse_args()

    manifest_path = (args.dir / "manifest.json") if args.dir else find_latest_manifest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = manifest_path.parent

    print(f"Manifesto: {manifest_path}")
    print(f"Carregando Whisper {args.model} (cpu/int8)...", flush=True)
    from faster_whisper import WhisperModel
    from services.model_manager import get_whisper_cache_dir

    whisper = WhisperModel(args.model, device="cpu", compute_type="int8",
                           download_root=str(get_whisper_cache_dir()))

    rows = []
    for sample in manifest["samples"]:
        wav_path = out_dir / sample["wav"]
        segments, info = whisper.transcribe(str(wav_path), beam_size=5,
                                            vad_filter=True, language="pt")
        hyp = " ".join(s.text.strip() for s in segments).strip()

        expected = content_words(sample["text"])
        got = content_words(hyp)
        recovered = expected & got
        ratio = (len(recovered) / len(expected)) if expected else 0.0
        passed = ratio >= args.pass_threshold

        sample["intelligibility_gate"] = {
            "model": args.model,
            "transcription": hyp,
            "content_words_expected": len(expected),
            "content_words_recovered": len(recovered),
            "recovery_ratio": round(ratio, 3),
            "missing": sorted(expected - got),
            "passed": passed,
        }
        rows.append((sample["id"], ratio, passed, hyp))

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n| Amostra | Recuperacao | Gate | Transcricao Whisper large-v3 |")
    print("|---|---:|---|---|")
    for sid, ratio, passed, hyp in rows:
        print(f"| {sid} | {ratio*100:.0f}% | {'PASSA' if passed else 'REPROVA'} | {hyp or '(vazio)'} |")

    n_pass = sum(1 for _, _, p, _ in rows if p)
    overall = "MADURA (inteligivel)" if n_pass == len(rows) else "IMATURA (nao inteligivel)"
    print(f"\nGate geral: {overall} — {n_pass}/{len(rows)} amostras inteligiveis.")
    print(f"Manifesto atualizado: {manifest_path}")
    return 0 if n_pass == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
