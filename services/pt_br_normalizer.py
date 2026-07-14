"""Normalizacao textual PT-BR compartilhada pelo pipeline TTS."""

import re
from typing import Callable, Dict


class TextNormalizationError(ValueError):
    """Falha explicita ao selecionar ou aplicar um perfil de normalizacao."""


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


def _normalize_default_pt_br(text: str) -> str:
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



_PROFILE_ALIASES: Dict[str, str] = {
    "default": "default",
    "tts_1_5b": "default",
    "vibevoice_1_5b": "default",
    "chatterbox_pt_br": "default",
}


def normalize_pt_br(text: str, *, profile: str = "default") -> str:
    """Normaliza texto com um perfil explicito, sem alterar a entrada original."""
    canonical = _PROFILE_ALIASES.get(str(profile or "default"))
    if canonical != "default":
        raise TextNormalizationError(f"Perfil de normalizacao desconhecido: {profile}.")
    return _normalize_default_pt_br(text)
