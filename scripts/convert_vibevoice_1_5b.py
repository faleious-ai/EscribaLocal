"""Converte o checkpoint oficial microsoft/VibeVoice-1.5B para o formato HF
que o fork em custom_transformers/ carrega.

Por que isso é necessário: o checkpoint publicado no HuggingFace está no
formato ORIGINAL do VibeVoice (chaves como `decoder_config`, pesos
`prediction_head.*`, convs aninhadas). O fork local só carrega o formato
convertido — sem a conversão, os tokenizers de áudio e o diffusion head ficam
com pesos aleatórios e o TTS produz fallback/ruído.

Uso (uma vez por máquina; requer o microsoft/VibeVoice-1.5B já baixado e
rede para buscar o tokenizer Qwen):

    .venv\\Scripts\\python.exe scripts\\convert_vibevoice_1_5b.py

Saída: models/VibeVoice-1.5B-hf/ (~5.4GB). O serviço de TTS usa esta pasta
automaticamente quando ela existe.
"""
import importlib
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

from services.transformers_loader import use_custom_transformers

SOURCE_REPO_DIRNAME = "models--microsoft--VibeVoice-1.5B"
OUTPUT_DIR = PROJECT_ROOT / "models" / "VibeVoice-1.5B-hf"


def find_snapshot() -> Path:
    from services.model_manager import get_hf_cache_dir

    snapshots_dir = get_hf_cache_dir() / SOURCE_REPO_DIRNAME / "snapshots"
    if not snapshots_dir.is_dir():
        raise SystemExit(
            "Checkpoint microsoft/VibeVoice-1.5B não encontrado no cache. "
            "Baixe-o primeiro pelo painel 'Modelos' do EscribaLocal."
        )
    snapshots = sorted(path for path in snapshots_dir.iterdir() if path.is_dir())
    if not snapshots:
        raise SystemExit("Nenhum snapshot do VibeVoice-1.5B no cache.")
    return snapshots[-1]


def main() -> None:
    snapshot = find_snapshot()
    print("snapshot de origem:", snapshot)
    if (OUTPUT_DIR / "config.json").exists():
        print("Saída já existe em", OUTPUT_DIR, "— nada a fazer.")
        return
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    with use_custom_transformers():
        from safetensors.torch import load_file

        merged_state = {}
        for shard in sorted(snapshot.glob("model-*.safetensors")):
            print("lendo shard:", shard.name)
            merged_state.update(load_file(str(shard)))
        print(f"{len(merged_state)} tensores carregados em {time.time() - started:.0f}s")

        converter = importlib.import_module(
            "transformers.models.vibevoice.convert_vibevoice_to_hf"
        )
        # O script original espera UM arquivo safetensors combinado; injetamos
        # o merge dos shards. O caminho fake mantém "1.5B" no nome porque o
        # script o usa para escolher o tokenizer Qwen correto.
        converter.load_file = lambda _path: merged_state
        converter.convert_checkpoint(
            checkpoint=str(snapshot / "VibeVoice-1.5B-combined.safetensors"),
            output_dir=str(OUTPUT_DIR),
            config_path=str(snapshot / "config.json"),
            push_to_hub=None,
            bfloat16=True,
            processor_config=str(snapshot / "preprocessor_config.json"),
        )

    print(f"CONVERSAO OK -> {OUTPUT_DIR} ({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
