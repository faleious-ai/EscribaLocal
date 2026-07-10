"""Orquestração pura antes das engines TTS.

Esta camada transforma roteiro livre em conteúdo pronto para fala: resolve
speakers, interpreta tags suportadas, normaliza casos comuns de PT-BR e
segmenta sem deixar instruções literais vazarem para a engine.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class TtsOrchestrationError(ValueError):
    pass


@dataclass(frozen=True)
class TtsSegment:
    speaker_number: str
    speaker_id: str
    text: str
    voice_id: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TtsPlan:
    engine_script: str
    segments: List[TtsSegment]
    tags: List[Dict[str, str]]


@dataclass
class ScriptNode:
    kind: str
    text: str = ""
    parameters: Dict[str, str] = field(default_factory=dict)
    children: List["ScriptNode"] = field(default_factory=list)
    line: int = 1
    column: int = 1


@dataclass
class ScriptAst:
    nodes: List[ScriptNode]


_canonical_tag_pattern = re.compile(r"^\[([a-zA-Z_][\w-]*)(.*?)\]$")
_canonical_close_pattern = re.compile(r"^\[/([a-zA-Z_][\w-]*)\]$")


def parse_script(script: str) -> ScriptAst:
    """Parseia a gramática canônica de T4.1 sem resolver a biblioteca."""
    root: List[ScriptNode] = []
    stack: List[ScriptNode] = []

    def append(node: ScriptNode) -> None:
        (stack[-1].children if stack else root).append(node)

    for line_no, raw in enumerate(script.replace("\r\n", "\n").split("\n"), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            append(ScriptNode("subtitle", text=line[2:].strip(), line=line_no))
            continue
        closing = _canonical_close_pattern.match(line)
        if closing:
            if not stack or stack[-1].text != closing.group(1):
                raise TtsOrchestrationError(f"Fechamento de estilo inválido na linha {line_no}, coluna 1.")
            stack.pop()
            continue
        match = _canonical_tag_pattern.match(line)
        if match:
            name, tail = match.group(1), match.group(2).strip()
            if name == "pausa":
                if not re.fullmatch(r"\d+(?:\.\d+)?(?:ms|s)", tail):
                    raise TtsOrchestrationError(f"Duração de pausa inválida na linha {line_no}, coluna 1.")
                append(ScriptNode("pause", text=tail, line=line_no))
                continue
            if name in {"respiracao", "suspiro", "risada"}:
                append(ScriptNode("event", text=name, parameters={"modificador": tail} if tail else {}, line=line_no))
                continue
            params = dict(re.findall(r"([\w-]+)=([^\s]+)", tail))
            node = ScriptNode("style", text=name, parameters=params, line=line_no)
            append(node)
            stack.append(node)
            continue
        append(ScriptNode("text", text=line, line=line_no))
    if stack:
        node = stack[-1]
        raise TtsOrchestrationError(f"Estilo '{node.text}' sem fechamento na linha {node.line}, coluna 1.")
    return ScriptAst(root)


def _canonical_spoken_text(script: str) -> str:
    def collect(nodes: List[ScriptNode]) -> List[str]:
        spoken: List[str] = []
        for node in nodes:
            if node.kind == "text":
                spoken.append(node.text)
            elif node.kind == "style":
                spoken.extend(collect(node.children))
        return spoken
    return " ".join(collect(parse_script(script).nodes))


_speaker_line_pattern = re.compile(r"^(?:voz|voice|speaker)\s*([0-9]+)\s*:\s*(.*)$", re.IGNORECASE)
_tag_pattern = re.compile(r"\[([a-zA-Z_][\w-]*)(?::([^\]]+))?\]")
_valid_tags = {"style", "pause"}

_months = {
    1: "janeiro",
    2: "fevereiro",
    3: "marco",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

_units = {
    0: "zero",
    1: "um",
    2: "dois",
    3: "tres",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
    10: "dez",
    11: "onze",
    12: "doze",
    13: "treze",
    14: "quatorze",
    15: "quinze",
    16: "dezesseis",
    17: "dezessete",
    18: "dezoito",
    19: "dezenove",
}
_tens = {
    20: "vinte",
    30: "trinta",
    40: "quarenta",
    50: "cinquenta",
    60: "sessenta",
    70: "setenta",
    80: "oitenta",
    90: "noventa",
}
_hundreds = {
    100: "cento",
    200: "duzentos",
    300: "trezentos",
    400: "quatrocentos",
    500: "quinhentos",
    600: "seiscentos",
    700: "setecentos",
    800: "oitocentos",
    900: "novecentos",
}


def _number_to_words(value: int) -> str:
    if value < 0:
        return "menos " + _number_to_words(abs(value))
    if value < 20:
        return _units[value]
    if value < 100:
        ten = (value // 10) * 10
        rest = value % 10
        return _tens[ten] if rest == 0 else f"{_tens[ten]} e {_units[rest]}"
    if value == 100:
        return "cem"
    if value < 1000:
        hundred = (value // 100) * 100
        rest = value % 100
        return _hundreds[hundred] if rest == 0 else f"{_hundreds[hundred]} e {_number_to_words(rest)}"
    if value < 10000:
        thousands = value // 1000
        rest = value % 1000
        prefix = "mil" if thousands == 1 else f"{_number_to_words(thousands)} mil"
        return prefix if rest == 0 else f"{prefix} e {_number_to_words(rest)}"
    return str(value)


def normalize_pt_br(text: str) -> str:
    text = re.sub(r"\bDra\.", "doutora", text)
    text = re.sub(r"\bDr\.", "doutor", text)
    text = re.sub(r"\bSra\.", "senhora", text)
    text = re.sub(r"\bSr\.", "senhor", text)

    def replace_currency(match: re.Match) -> str:
        reais = int(match.group(1).replace(".", ""))
        centavos = int(match.group(2))
        return f"{_number_to_words(reais)} reais e {_number_to_words(centavos)} centavos"

    text = re.sub(r"R\$\s*([0-9.]+),([0-9]{2})", replace_currency, text)

    def replace_date(match: re.Match) -> str:
        day = int(match.group(1))
        month = int(match.group(2))
        if month not in _months:
            return match.group(0)
        return f"{_number_to_words(day)} de {_months[month]}"

    text = re.sub(r"\b([0-9]{1,2})/([0-9]{1,2})(?:/[0-9]{2,4})?\b", replace_date, text)
    text = re.sub(r"\b[0-9]+\b", lambda m: _number_to_words(int(m.group(0))), text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([.,!?;:])", r"\1", text)


def _speaker_id_for_number(number: str, default_speaker_id: str) -> str:
    if number == "0":
        return default_speaker_id
    if number in {"1", "2", "3", "4"}:
        return f"speaker_{number}"
    raise TtsOrchestrationError("O TTS suporta no maximo 4 speakers por roteiro.")


def _collect_lines(text: str, default_speaker_id: str) -> List[tuple[str, str]]:
    current = re.search(r"([0-9]+)$", default_speaker_id or "")
    current_number = current.group(1) if current else "1"
    lines: List[tuple[str, str]] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        match = _speaker_line_pattern.match(line)
        if match:
            current_number = match.group(1)
            _speaker_id_for_number(current_number, default_speaker_id)
            if match.group(2).strip():
                lines.append((current_number, match.group(2).strip()))
        elif lines:
            number, previous = lines[-1]
            lines[-1] = (number, f"{previous} {line}")
        else:
            lines.append((current_number, line))
    if not lines:
        lines.append((current_number, text.strip()))
    return lines


def _has_explicit_speaker_markup(text: str) -> bool:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return any(
        _speaker_line_pattern.match(line.strip())
        for line in normalized.split("\n")
        if line.strip()
    )


def _strip_tags(text: str) -> tuple[str, Dict[str, str], List[Dict[str, str]]]:
    style: Dict[str, str] = {}
    tags: List[Dict[str, str]] = []

    def replace(match: re.Match) -> str:
        name = match.group(1).lower()
        value = (match.group(2) or "").strip()
        if name not in _valid_tags:
            raise TtsOrchestrationError(f"Tag invalida no roteiro TTS: [{name}]")
        tags.append({"name": name, "value": value})
        if name == "style" and value:
            style["style"] = value
        return " "

    cleaned = _tag_pattern.sub(replace, text)
    return re.sub(r"\s+", " ", cleaned).strip(), style, tags


def _split_text(text: str, max_segment_chars: int) -> List[str]:
    if len(text) <= max_segment_chars:
        return [text]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    chunks: List[str] = []
    current = ""
    for sentence in sentences or [text]:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_segment_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def orchestrate_tts(
    text: str,
    default_speaker_id: str = "speaker_1",
    speaker_voices: Optional[Dict[str, str]] = None,
    max_segment_chars: int = 500,
) -> TtsPlan:
    if not text or not text.strip():
        raise TtsOrchestrationError("Informe um texto para gerar voz.")

    # A forma canônica possui fechamento explícito; reduza-a para texto falado
    # antes do pipeline legado, preservando a garantia de não vazar tags.
    if "[/" in text:
        text = _canonical_spoken_text(text)

    all_tags: List[Dict[str, str]] = []
    segments: List[TtsSegment] = []
    for number, raw_text in _collect_lines(text, default_speaker_id):
        clean_text, style, tags = _strip_tags(raw_text)
        all_tags.extend(tags)
        spoken_text = normalize_pt_br(clean_text)
        for chunk in _split_text(spoken_text, max_segment_chars):
            segments.append(TtsSegment(
                speaker_number=number,
                speaker_id=_speaker_id_for_number(number, default_speaker_id),
                voice_id=(speaker_voices or {}).get(number),
                text=chunk,
                style=style,
            ))

    unique_speakers = {segment.speaker_number for segment in segments if segment.text}
    has_explicit_speakers = _has_explicit_speaker_markup(text)
    if len(unique_speakers) <= 1 and not has_explicit_speakers:
        engine_script = " ".join(segment.text for segment in segments if segment.text).strip()
    else:
        engine_script = "\n".join(
            f"Speaker {segment.speaker_number}: {segment.text}"
            for segment in segments if segment.text
        )
    return TtsPlan(engine_script=engine_script, segments=segments, tags=all_tags)
