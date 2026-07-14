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
