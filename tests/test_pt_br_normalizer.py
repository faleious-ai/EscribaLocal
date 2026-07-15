import pytest

from services.pt_br_normalizer import TextNormalizationError, normalize_pt_br


def test_default_profile_preserves_existing_normalization_contract():
    assert normalize_pt_br("Dra. Ana pagou R$ 12,50 em 10/05 e tem 2 gatos.") == (
        "doutora Ana pagou doze reais e cinquenta centavos em dez de maio e tem dois gatos."
    )


@pytest.mark.parametrize("profile", ["default", "tts_1_5b", "vibevoice_1_5b", "chatterbox_pt_br"])
def test_known_engine_profiles_share_current_rules(profile):
    assert normalize_pt_br("Sr. Joao tem 2 gatos.", profile=profile) == "senhor Joao tem dois gatos."


def test_unknown_profile_fails_explicitly():
    with pytest.raises(TextNormalizationError, match="Perfil de normalizacao desconhecido"):
        normalize_pt_br("Ola.", profile="engine-inexistente")


def test_normalizes_full_date_with_year_and_accents():
    assert normalize_pt_br("A reunião é em 03/08/2026.") == "A reunião é em três de agosto de dois mil e vinte e seis."


def test_normalizes_time_without_treating_it_as_generic_numbers():
    assert normalize_pt_br("A gravação começa às 14:30.") == "A gravação começa às quatorze horas e trinta minutos."


def test_normalizes_currency_percentages_and_common_units_with_agreement():
    assert normalize_pt_br("Custam R$ 1,01, medem 2 kg e cresceram 12,5%.") == (
        "Custam um real e um centavo, medem dois quilogramas e cresceram doze vírgula cinco por cento."
    )


def test_currency_omits_zero_cents_and_uses_singular_currency_labels():
    assert normalize_pt_br("O ingresso custa R$ 1,00.") == "O ingresso custa um real."


def test_keeps_urls_emails_and_phones_intact_while_expanding_configured_terms():
    text = "A API do Escriba atende em https://exemplo.com/123, suporte@exemplo.com e (11) 99876-5432."
    assert normalize_pt_br(
        text,
        acronyms={"API": "a p i"},
        user_dictionary={"Escriba": "Escriba Local"},
    ) == "A a p i do Escriba Local atende em https://exemplo.com/123, suporte@exemplo.com e (11) 99876-5432."


def test_expands_abbreviations_and_supported_large_numbers_but_keeps_larger_values_explicit():
    assert normalize_pt_br("Prof. João catalogou 1.234.567 itens e 1.000.000.000 pendências.") == (
        "professor João catalogou um milhão e duzentos e trinta e quatro mil e quinhentos e sessenta e sete itens e 1.000.000.000 pendências."
    )
