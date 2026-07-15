"""Gera o conjunto auditável de amostras T8.5 do Chatterbox PT-BR.

As amostras e o manifesto são artefatos locais de QA (``data/`` é ignorado pelo
Git). A naturalidade ainda precisa de escuta humana; este script só automatiza
a geração, a validação estrutural e a preservação dos metadados usados.

Uso:
  .venv\\Scripts\\python.exe scripts\\qa_chatterbox_pt_br.py
  .venv\\Scripts\\python.exe scripts\\qa_chatterbox_pt_br.py --dry-run
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services import voice_profiles
from services.vibevoice_tts_1_5b import generate_voice_1_5b_with_metadata


SAMPLES = (
    {
        "id": "neutro",
        "text": "Bom dia. Esta é uma amostra neutra de voz em português brasileiro.",
        "parameters": {},
    },
    {
        "id": "estilo_contido",
        "text": "Atenção: esta mensagem usa uma expressão mais contida.",
        "parameters": {"exaggeration": 0.3, "cfg_weight": 0.65},
    },
    {
        "id": "estilo_expressivo",
        "text": "Que notícia maravilhosa! Vamos comemorar juntos.",
        "parameters": {"exaggeration": 0.85, "cfg_weight": 0.35},
    },
    {
        "id": "numeros",
        "text": "Em quinze de julho de dois mil e vinte e seis, pagamos cento e vinte e três reais e quarenta e cinco centavos, ou 12,5 por cento do total.",
        "parameters": {},
    },
    {
        "id": "texto_longo",
        "text": "Este texto longo verifica a segmentação do Chatterbox em várias partes. "
        "Cada parte deve manter a mesma voz de referência, preservar a inteligibilidade "
        "e evitar cortes abruptos entre as frases. O resultado será avaliado por escuta "
        "humana quanto a naturalidade, prosódia, ritmo, pronúncia e artefatos.",
        "parameters": {},
    },
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if key != "wav_bytes"}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _inspect_wav(wav_bytes: bytes) -> dict[str, Any]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        info = {
            "sample_rate": wav.getframerate(),
            "channels": wav.getnchannels(),
            "sample_width": wav.getsampwidth(),
            "frames": wav.getnframes(),
        }
    if info["sample_rate"] != 24000 or info["channels"] != 1 or info["sample_width"] != 2:
        raise RuntimeError(f"WAV fora do contrato TTS: {info}")
    if info["frames"] <= 0:
        raise RuntimeError("WAV sem frames de áudio.")
    info["duration_seconds"] = round(info["frames"] / info["sample_rate"], 3)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-id", help="ID da voz real; por padrão usa a voz padrão local.")
    parser.add_argument("--output-dir", type=Path, help="Diretório das amostras (padrão: data/tts_qa/chatterbox-<timestamp>).")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--limit", type=int, help="Gera somente as primeiras N amostras.")
    parser.add_argument("--dry-run", action="store_true", help="Lista o plano sem carregar modelo nem gerar áudio.")
    args = parser.parse_args()

    voice_id = args.voice_id or voice_profiles.get_default_voice_id()
    if not voice_id:
        raise SystemExit("Nenhuma voz real padrão encontrada; use --voice-id.")

    samples = list(SAMPLES[: args.limit] if args.limit is not None else SAMPLES)
    if not samples:
        raise SystemExit("--limit deve ser maior que zero.")

    if args.dry_run:
        print(json.dumps({"voice_id": voice_id, "samples": samples}, ensure_ascii=False, indent=2))
        return 0

    output_dir = args.output_dir or PROJECT_ROOT / "data" / "tts_qa" / (
        "chatterbox-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "tts-qa-chatterbox-v1",
        "engine": "chatterbox-tts-pt-br",
        "voice_id": voice_id,
        "generated_at": datetime.now().astimezone().isoformat(),
        "samples": [],
    }

    for sample in samples:
        print(f"Gerando {sample['id']}...", flush=True)
        result = generate_voice_1_5b_with_metadata(
            text=sample["text"],
            model_key="chatterbox-tts-pt-br",
            voice_id=voice_id,
            chatterbox_parameters=sample["parameters"],
            failure_policy="fail",
            device=args.device,
            unload_after=True,
        )
        audio_info = _inspect_wav(result["wav_bytes"])
        wav_path = output_dir / f"{sample['id']}.wav"
        wav_path.write_bytes(result["wav_bytes"])
        manifest["samples"].append({
            "id": sample["id"],
            "text": sample["text"],
            "parameters_requested": sample["parameters"],
            "wav": wav_path.name,
            "audio": audio_info,
            "metadata": _json_safe(result),
            "human_audit": {
                "naturalidade": None,
                "prosodia": None,
                "pronuncia": None,
                "artefatos": None,
                "observacoes": "Preencher após escuta humana.",
            },
        })

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
