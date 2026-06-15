import importlib.util
import logging
import os
import tempfile
import numpy as np
import scipy.io.wavfile as wavfile
import torch
from typing import Any, Dict, Optional

from services.app_logging import record_exception_event
from services.resource_arbiter import arbiter

logger = logging.getLogger("EscribaLocal.ChatterboxAdapter")


class ChatterboxUnavailableError(RuntimeError):
    pass


class ChatterboxAdapter:
    def __init__(self):
        self.model = None
        self._device = "cpu"

    def is_loaded(self) -> bool:
        return self.model is not None

    def unload(self) -> None:
        if self.model is not None:
            logger.info("Chatterbox: liberando modelo da memoria...")
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def est_vram_mb(self) -> float:
        return 1500.0

    def current_model(self) -> Optional[str]:
        if self.model is not None:
            return "ResembleAI/Chatterbox-Multilingual-pt-br"
        return None

    def _ensure_model(self):
        if self.model is not None:
            return

        if importlib.util.find_spec("chatterbox") is None:
            raise ChatterboxUnavailableError(
                "Chatterbox-TTS indisponivel: biblioteca 'chatterbox-tts' ausente. "
                "Instale a biblioteca 'chatterbox-tts' em seu ambiente para usar esta engine."
            )

        arbiter.prepare_load("tts_chatterbox")
        
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except ImportError:
            try:
                from chatterbox.tts import ChatterboxTTS as ChatterboxMultilingualTTS
            except ImportError as exc:
                raise ChatterboxUnavailableError(
                    f"Chatterbox-TTS indisponivel: falha ao importar classes do pacote chatterbox: {exc}"
                )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device
        
        logger.info("Carregando Chatterbox PT-BR no device %s...", device)
        from services.model_manager import get_spec
        spec = get_spec("chatterbox-tts-pt-br")
        
        self.model = ChatterboxMultilingualTTS.from_pretrained(
            spec.repo_id,
            device=device
        )
        logger.info("Chatterbox PT-BR carregado com sucesso.")

    def generate_voice_chatterbox(
        self,
        text: str,
        voice_id: Optional[str] = None,
        speaker_voices: Optional[Dict[str, str]] = None,
        speaker_id: str = "speaker_1",
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        self._ensure_model()
        
        from services import voice_profiles
        from services.vibevoice_tts_1_5b import VoiceUnavailableError, _voice_reference_waveform, _wav_bytes_from_array
        
        resolved_voice_id = None
        if speaker_voices and speaker_id:
            import re
            m = re.search(r"([0-9]+)$", speaker_id)
            num = m.group(1) if m else "1"
            resolved_voice_id = speaker_voices.get(num)
            
        if not resolved_voice_id:
            resolved_voice_id = voice_id
            
        if not resolved_voice_id:
            resolved_voice_id = voice_profiles.get_default_voice_id()
            
        if not resolved_voice_id:
            raise VoiceUnavailableError("Nenhuma voz de referência foi selecionada ou encontrada para o Chatterbox.")

        resolved = voice_profiles.resolve_voice_id(resolved_voice_id)
        
        temp_paths = []
        try:
            if voice_profiles.is_preset(resolved):
                preset_spec = next((p for p in voice_profiles.PRESET_VOICES if p["id"] == resolved), None)
                if not preset_spec:
                    raise VoiceUnavailableError(f"Preset {resolved} não encontrado.")
                
                speaker_hint = preset_spec["speaker_hint"]
                waveform = _voice_reference_waveform(speaker_hint)
                if waveform is None:
                    raise VoiceUnavailableError(f"Preset {resolved} indisponível (SAPI5 não respondeu).")
                
                fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                temp_paths.append(temp_wav)
                
                wavfile.write(temp_wav, 24000, waveform)
                ref_path = temp_wav
            else:
                try:
                    _profile = voice_profiles.get_voice(resolved)
                    ref_path = str(voice_profiles.reference_path(resolved))
                    if not os.path.exists(ref_path):
                        raise VoiceUnavailableError(f"Arquivo de voz {resolved} ausente no disco.")
                except Exception as exc:
                    raise VoiceUnavailableError(f"Voz {resolved} indisponível: {exc}")

            kwargs = {}
            if hasattr(self.model, "generate"):
                import inspect
                sig = inspect.signature(self.model.generate)
                if "language_id" in sig.parameters:
                    kwargs["language_id"] = "pt"
                elif "language" in sig.parameters:
                    kwargs["language"] = "pt"
                
                audio_tensor = self.model.generate(
                    text=text,
                    audio_prompt_path=ref_path,
                    **kwargs
                )
            else:
                raise RuntimeError("O modelo Chatterbox não possui o método generate.")

            if isinstance(audio_tensor, torch.Tensor):
                audio_np = audio_tensor.detach().cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)
                
            sample_rate = getattr(self.model, "sr", 24000)
            wav_bytes = _wav_bytes_from_array(audio_np, sample_rate=sample_rate, speed=speed)
            
            return {
                "wav_bytes": wav_bytes,
                "engine_key": "chatterbox-tts-pt-br",
                "engine_label": "Chatterbox PT-BR",
                "fallback": False,
            }
        finally:
            for p in temp_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass


chatterbox_engine = ChatterboxAdapter()

arbiter.register_engine(
    engine="tts_chatterbox",
    label="Chatterbox PT-BR",
    is_loaded=lambda: chatterbox_engine.is_loaded(),
    unload=lambda: chatterbox_engine.unload(),
    est_vram_mb=lambda: chatterbox_engine.est_vram_mb(),
    current_model=lambda: chatterbox_engine.current_model(),
)
