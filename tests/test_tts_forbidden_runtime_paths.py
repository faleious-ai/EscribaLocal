import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "routers",
    PROJECT_ROOT / "services",
    PROJECT_ROOT / "workers",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "static",
)

FORBIDDEN_RUNTIME_PATTERNS = {
    "win32com import/call": re.compile(r"\bwin32com(?:\.client)?\b"),
    "pyttsx3": re.compile(r"\bpyttsx3\b"),
    "System.Speech": re.compile(r"\bSystem\.Speech\b"),
    "SAPI COM objects": re.compile(r"\bSp(?:Voice|FileStream|MemoryStream)\b"),
    "Windows preset catalog": re.compile(r"\bPRESET_VOICES\b|\bPRESET_IDS\b|Preset local"),
    "sine prompt generator": re.compile(r"_write_sine|math\.sin\s*\(|np\.sin\s*\("),
    "synthetic smoke generator": re.compile(
        r"_synthetic_smoke_(?:enabled|response|pcm_bytes)|synthetic_smoke_enabled"
    ),
}


def _production_files():
    for root in PRODUCTION_ROOTS:
        if root.is_file():
            yield root
        elif root.is_dir():
            yield from root.rglob("*")


def test_tts_production_runtime_has_no_forbidden_audio_paths():
    hits = []
    for path in _production_files():
        if path.suffix.lower() not in {".py", ".js", ".html"}:
            continue
        source = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_RUNTIME_PATTERNS.items():
            if pattern.search(source):
                hits.append(f"{path.relative_to(PROJECT_ROOT)}: {label}")

    assert hits == []
