"""Normalizacao textual PT-BR compartilhada pelo pipeline TTS."""

import re
from typing import Dict, Mapping, Optional


class TextNormalizationError(ValueError):
    """Falha explicita ao selecionar ou aplicar um perfil de normalizacao."""


_months = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
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
    3: "três",
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

_COMMON_UNITS = {
    "kg": ("quilograma", "quilogramas"),
    "g": ("grama", "gramas"),
    "m": ("metro", "metros"),
    "cm": ("centímetro", "centímetros"),
    "km": ("quilômetro", "quilômetros"),
    "l": ("litro", "litros"),
    "ml": ("mililitro", "mililitros"),
}

_MAX_SPOKEN_NUMBER = 999_999_999


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
    if value < 1_000_000:
        thousands = value // 1000
        rest = value % 1000
        prefix = "mil" if thousands == 1 else f"{_number_to_words(thousands)} mil"
        return prefix if rest == 0 else f"{prefix} e {_number_to_words(rest)}"
    if value <= _MAX_SPOKEN_NUMBER:
        millions = value // 1_000_000
        rest = value % 1_000_000
        prefix = "um milhão" if millions == 1 else f"{_number_to_words(millions)} milhões"
        return prefix if rest == 0 else f"{prefix} e {_number_to_words(rest)}"
    return str(value)


def _protect_literals(text: str):
    protected = []

    def replace(match: re.Match) -> str:
        token = f"PROTECTEDLITERAL{chr(ord('A') + len(protected))}TOKEN"
        protected.append((token, match.group(0)))
        return token

    literal_pattern = re.compile(
        r"https?://[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+55\s*)?\(?\d{2}\)?\s?\d{4,5}-\d{4}"
    )
    return literal_pattern.sub(replace, text), protected


def _normalize_default_pt_br(
    text: str,
    *,
    acronyms: Optional[Mapping[str, str]] = None,
    user_dictionary: Optional[Mapping[str, str]] = None,
) -> str:
    for source, replacement in (user_dictionary or {}).items():
        text = re.sub(rf"\b{re.escape(str(source))}\b", str(replacement), text)
    for acronym, pronunciation in (acronyms or {}).items():
        text = re.sub(rf"\b{re.escape(str(acronym))}\b", str(pronunciation), text)

    text, protected = _protect_literals(text)
    text = re.sub(r"\bDra\.", "doutora", text)
    text = re.sub(r"\bDr\.", "doutor", text)
    text = re.sub(r"\bSra\.", "senhora", text)
    text = re.sub(r"\bSr\.", "senhor", text)
    text = re.sub(r"\bProf\.ª", "professora", text)
    text = re.sub(r"\bProf\.", "professor", text)

    def replace_currency(match: re.Match) -> str:
        reais = int(match.group(1).replace(".", ""))
        centavos = int(match.group(2))
        real_label = "real" if reais == 1 else "reais"
        cent_label = "centavo" if centavos == 1 else "centavos"
        reais_text = f"{_number_to_words(reais)} {real_label}"
        return reais_text if centavos == 0 else f"{reais_text} e {_number_to_words(centavos)} {cent_label}"

    text = re.sub(r"R\$\s*([0-9.]+),([0-9]{2})", replace_currency, text)

    def replace_date(match: re.Match) -> str:
        day = int(match.group(1))
        month = int(match.group(2))
        if month not in _months:
            return match.group(0)
        year = match.group(3)
        date = f"{_number_to_words(day)} de {_months[month]}"
        return f"{date} de {_number_to_words(int(year))}" if year else date

    text = re.sub(r"\b([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{4}))?\b", replace_date, text)

    def replace_time(match: re.Match) -> str:
        hour = _number_to_words(int(match.group(1)))
        minute = int(match.group(2))
        return f"{hour} horas" if minute == 0 else f"{hour} horas e {_number_to_words(minute)} minutos"

    text = re.sub(r"\b([0-2]?[0-9]):([0-5][0-9])\b", replace_time, text)

    def replace_percentage(match: re.Match) -> str:
        whole, fraction = match.groups()
        fraction_words = " ".join(_number_to_words(int(digit)) for digit in fraction)
        return f"{_number_to_words(int(whole))} vírgula {fraction_words} por cento"

    text = re.sub(r"\b([0-9]+),([0-9]+)%", replace_percentage, text)

    def replace_unit(match: re.Match) -> str:
        value = int(match.group(1))
        singular, plural = _COMMON_UNITS[match.group(2).lower()]
        return f"{_number_to_words(value)} {singular if value == 1 else plural}"

    text = re.sub(r"\b([0-9]+)\s*(kg|g|km|cm|m|ml|l)\b", replace_unit, text, flags=re.IGNORECASE)
    overflow_numbers = {}

    def protect_overflow_number(match: re.Match) -> str:
        value = int(match.group(0).replace(".", ""))
        if value <= _MAX_SPOKEN_NUMBER:
            return match.group(0)
        token = f"OVERFLOWNUMBER{chr(ord('A') + len(overflow_numbers))}TOKEN"
        overflow_numbers[token] = match.group(0)
        return token

    text = re.sub(r"\b[0-9]{1,3}(?:\.[0-9]{3})+\b", protect_overflow_number, text)

    def replace_grouped_number(match: re.Match) -> str:
        value = int(match.group(0).replace(".", ""))
        return _number_to_words(value) if value <= _MAX_SPOKEN_NUMBER else match.group(0)

    text = re.sub(r"\b[0-9]{1,3}(?:\.[0-9]{3})+\b", replace_grouped_number, text)
    text = re.sub(r"\b[0-9]+\b", lambda m: _number_to_words(int(m.group(0))), text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    for token, literal in protected:
        text = text.replace(token, literal)
    for token, literal in overflow_numbers.items():
        text = text.replace(token, literal)
    return text



_PROFILE_ALIASES: Dict[str, str] = {
    "default": "default",
    "tts_1_5b": "default",
    "vibevoice_1_5b": "default",
    "chatterbox_pt_br": "default",
}


def normalize_pt_br(
    text: str,
    *,
    profile: str = "default",
    acronyms: Optional[Mapping[str, str]] = None,
    user_dictionary: Optional[Mapping[str, str]] = None,
) -> str:
    """Normaliza texto com um perfil explicito, sem alterar a entrada original."""
    canonical = _PROFILE_ALIASES.get(str(profile or "default"))
    if canonical != "default":
        raise TextNormalizationError(f"Perfil de normalizacao desconhecido: {profile}.")
    return _normalize_default_pt_br(text, acronyms=acronyms, user_dictionary=user_dictionary)
