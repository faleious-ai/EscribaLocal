"""Orquestração pura antes das engines TTS.

Esta camada transforma roteiro livre em conteúdo pronto para fala: resolve
speakers, interpreta tags suportadas, normaliza casos comuns de PT-BR e
segmenta sem deixar instruções literais vazarem para a engine.
"""
import re
import hashlib
from dataclasses import dataclass, field
from pathlib import PurePath, PureWindowsPath
from typing import Dict, List, Optional


from services.pt_br_normalizer import normalize_pt_br

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


@dataclass(frozen=True)
class RenderJob:
    job_id: str
    order: int
    section_id: Optional[str]
    speaker_id: Optional[str]
    section_title: Optional[str]
    voice_id: str
    style_id: Optional[str]
    reference: Optional[str]
    parameters: Dict[str, object]
    original_text: str
    normalized_text: str
    pause_before_ms: int = 0
    events_before: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderPlan:
    version: int
    jobs: List[RenderJob]

    def manifest(self) -> Dict[str, object]:
        return {"version": self.version, "jobs": [job.__dict__ for job in self.jobs]}


def _typed_parameter(value: object) -> object:
    if not isinstance(value, str):
        return value
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def build_render_plan(
    ast: ScriptAst,
    *,
    voice_id: str,
    reference: Optional[str] = None,
    speaker_voices: Optional[Dict[str, str]] = None,
    engine_key: str = "tts_1_5b",
) -> RenderPlan:
    jobs: List[RenderJob] = []
    current_section_id: Optional[str] = None
    current_section_title: Optional[str] = None
    section_ordinal = 0
    pending_pause_ms = 0
    pending_events: List[str] = []

    if reference and (PurePath(reference).is_absolute() or PureWindowsPath(reference).is_absolute()):
        raise TtsOrchestrationError("RenderPlan exige referencia relativa controlada.")

    def section_id_for(title: str, ordinal: int) -> str:
        canonical = f"{ordinal}:{title.strip()}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def resolve_segment(style: Optional[ScriptNode]) -> tuple[Optional[str], str, Optional[str], Optional[str], Dict[str, object]]:
        from services import voice_profiles

        inline = dict(style.parameters) if style else {}
        speaker_id = inline.pop("falante", None)
        resolved_voice_id = voice_id
        if speaker_id:
            resolved_voice_id = (speaker_voices or {}).get(speaker_id) or ""
            if not resolved_voice_id:
                raise TtsOrchestrationError(f"Speaker sem voz: {speaker_id}.")

        if not style and not speaker_id:
            return None, resolved_voice_id, None, reference, {}
        if style and not speaker_id and reference is not None and speaker_voices is None:
            legacy_parameters = {key: _typed_parameter(value) for key, value in inline.items()}
            return None, resolved_voice_id, style.text, reference, legacy_parameters

        try:
            profile = voice_profiles.get_voice(resolved_voice_id)
        except Exception as exc:
            raise TtsOrchestrationError(f"Voz inexistente: {resolved_voice_id}.") from exc

        neutral = reference or ((profile.get("engines") or {}).get(engine_key) or {}).get("reference", {}).get("path")
        neutral = neutral or (profile.get("reference") or {}).get("path")
        if neutral and (PurePath(neutral).is_absolute() or PureWindowsPath(neutral).is_absolute()):
            raise TtsOrchestrationError("RenderPlan exige referencia relativa controlada.")

        if not style:
            return speaker_id, resolved_voice_id, None, neutral, {}

        items = (profile.get("styles") or {}).get("items") or []
        resolved_style = None
        for item in items:
            if style.text == item.get("style_id") or style.text in (item.get("aliases") or []):
                resolved_style = item
                break
        if not resolved_style or not resolved_style.get("active", True):
            raise TtsOrchestrationError(f"Estilo inexistente ou inativo: {style.text}.")
        compatibility = (resolved_style.get("engine_compatibility") or {}).get(engine_key)
        if compatibility in {"unsupported", "blocked"}:
            raise TtsOrchestrationError(f"Estilo incompat?vel com {engine_key}: {style.text}.")

        style_ref = resolved_style.get("reference") or {}
        resolved_reference = neutral
        if style_ref.get("status") == "ready":
            path = style_ref.get("path")
            if not path:
                raise TtsOrchestrationError(f"Refer?ncia pronta inconsistente: {style.text}.")
            media_path = voice_profiles.style_reference_path(resolved_voice_id, resolved_style["style_id"])
            if not media_path.exists():
                raise TtsOrchestrationError(f"M?dia de refer?ncia ausente: {style.text}.")
            resolved_reference = f"styles/{resolved_style['style_id']}/{path}"
        elif style_ref.get("status") not in {None, "missing", "pending"}:
            raise TtsOrchestrationError(f"Refer?ncia de estilo inv?lida: {style.text}.")

        if not resolved_reference:
            raise TtsOrchestrationError(f"Refer?ncia neutra ausente para voz: {resolved_voice_id}.")
        if PurePath(resolved_reference).is_absolute() or PureWindowsPath(resolved_reference).is_absolute():
            raise TtsOrchestrationError("RenderPlan exige referencia relativa controlada.")

        parameters = {key: _typed_parameter(value) for key, value in (resolved_style.get("parameters") or {}).items()}
        parameters.update({key: _typed_parameter(value) for key, value in inline.items()})
        return speaker_id, resolved_voice_id, resolved_style["style_id"], resolved_reference, parameters

    def walk(nodes: List[ScriptNode], style: Optional[ScriptNode] = None) -> None:
        nonlocal current_section_id, current_section_title, section_ordinal, pending_pause_ms, pending_events
        for node in nodes:
            if node.kind == "subtitle":
                section_ordinal += 1
                current_section_title = node.text
                current_section_id = section_id_for(node.text, section_ordinal)
            elif node.kind == "style":
                walk(node.children, node)
            elif node.kind == "pause":
                if node.text.endswith("ms"):
                    pending_pause_ms += int(float(node.text[:-2]))
                else:
                    pending_pause_ms += round(float(node.text[:-1]) * 1000)
            elif node.kind == "event":
                event_id = {"respiracao": "breath_short", "suspiro": "sigh", "risada": "laugh_soft"}.get(node.text)
                if event_id is None:
                    raise TtsOrchestrationError(f"Evento desconhecido: {node.text}.")
                pending_events.append(event_id)
            elif node.kind == "text":
                normalized = normalize_pt_br(node.text)
                order = len(jobs)
                speaker_id, resolved_voice_id, style_id, resolved_reference, parameters = resolve_segment(style)
                semantic_key = repr((
                    current_section_id, current_section_title, order, speaker_id, resolved_voice_id,
                    style_id, resolved_reference, sorted(parameters.items()), pending_pause_ms,
                    tuple(pending_events), node.text, normalized,
                ))
                jobs.append(RenderJob(
                    job_id=hashlib.sha256(semantic_key.encode("utf-8")).hexdigest()[:16],
                    order=order,
                    section_id=current_section_id,
                    speaker_id=speaker_id,
                    section_title=current_section_title,
                    voice_id=resolved_voice_id,
                    style_id=style_id,
                    reference=resolved_reference,
                    parameters=parameters,
                    original_text=node.text,
                    normalized_text=normalized,
                    pause_before_ms=pending_pause_ms,
                    events_before=tuple(pending_events),
                ))
                pending_pause_ms = 0
                pending_events = []

    walk(ast.nodes)
    return RenderPlan(version=1, jobs=jobs)


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


def _uses_canonical_script_syntax(script: str) -> bool:
    return (
        "[/" in script
        or any(line.strip().startswith(("##", "[pausa ", "[respiracao", "[suspiro", "[risada"))
               for line in script.splitlines())
    )


def validate_script_library(
    ast: ScriptAst,
    *,
    voice_id: str,
    engine_key: str = "tts_1_5b",
    speaker_voices: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """Resolve referências do AST sem gerar áudio ou montar plano de renderização."""
    from services import voice_profiles

    profile = voice_profiles.get_voice(voice_id)
    styles = (profile.get("styles") or {}).get("items") or []
    by_name = {item.get("style_id"): item for item in styles}
    for item in styles:
        for alias in item.get("aliases", []):
            by_name[alias] = item
    available_events = (profile.get("events") or {}).get("items") or {}
    event_ids = {"respiracao": "breath_short", "suspiro": "sigh", "risada": "laugh_soft"}
    resolved_styles: Dict[str, str] = {}
    resolved_events: List[str] = []

    def walk(nodes: List[ScriptNode]) -> None:
        for node in nodes:
            if node.kind == "style":
                speaker = node.parameters.get("falante")
                if speaker and not (speaker_voices or {}).get(speaker):
                    raise TtsOrchestrationError(f"Speaker sem voz na linha {node.line}, coluna {node.column}: {speaker}.")
                style = by_name.get(node.text)
                if not style or not style.get("active", True):
                    raise TtsOrchestrationError(f"Estilo inexistente na linha {node.line}, coluna {node.column}: {node.text}.")
                compatibility = (style.get("engine_compatibility") or {}).get(engine_key)
                if compatibility in {"unsupported", "blocked"}:
                    raise TtsOrchestrationError(f"Estilo incompatível com {engine_key} na linha {node.line}, coluna {node.column}.")
                resolved_styles[node.text] = style["style_id"]
                walk(node.children)
            elif node.kind == "event":
                event_id = event_ids[node.text]
                if event_id not in available_events:
                    raise TtsOrchestrationError(f"Evento ausente na linha {node.line}, coluna {node.column}: {node.text}.")
                resolved_events.append(event_id)

    walk(ast.nodes)
    return {"styles": resolved_styles, "events": resolved_events}


_speaker_line_pattern = re.compile(r"^(?:voz|voice|speaker)\s*([0-9]+)\s*:\s*(.*)$", re.IGNORECASE)
_tag_pattern = re.compile(r"\[([a-zA-Z_][\w-]*)(?::([^\]]+))?\]")
_valid_tags = {"style", "pause"}

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
    if _uses_canonical_script_syntax(text):
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
