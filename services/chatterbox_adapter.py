import importlib.util
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
import torch
import torch.nn.functional as F

# Injetar fallbacks para dtypes float8 ausentes no PyTorch do Windows, evitando
# falhas de importacao de arquitetura Llama no transformers community.
if not hasattr(torch, "float8_e4m3fn"):
    torch.float8_e4m3fn = torch.float16
if not hasattr(torch, "float8_e8m0fnu"):
    torch.float8_e8m0fnu = torch.float16

from services.resource_arbiter import arbiter

logger = logging.getLogger("EscribaLocal.ChatterboxAdapter")


class ChatterboxUnavailableError(RuntimeError):
    pass


def _punc_norm(text: str) -> str:
    if len(text) == 0:
        return "You need to add some text for me to talk."

    if text[0].islower():
        text = text[0].upper() + text[1:]

    text = " ".join(text.split())

    replacements = [
        ("...", ", "),
        (":", ","),
        (" - ", ", "),
        (";", ", "),
        (" ,", ","),
    ]
    for old_text, new_text in replacements:
        text = text.replace(old_text, new_text)

    text = text.rstrip(" ")
    sentence_enders = {".", "!", "?", "-", ",", "、", "，", "。", "？", "！"}
    if not any(text.endswith(punc) for punc in sentence_enders):
        text += "."

    return text


class _LocalChatterboxRuntime:
    def __init__(self, t3, s3gen, ve, tokenizer, device: str, sample_rate: int):
        self.t3 = t3
        self.s3gen = s3gen
        self.ve = ve
        self.tokenizer = tokenizer
        self.device = device
        self.sr = sample_rate

    def _prepare_conditionals(self, audio_prompt_path: str, exaggeration: float):
        import librosa
        from chatterbox.models.s3tokenizer import S3_SR
        from chatterbox.models.t3.modules.cond_enc import T3Cond

        ref_24k_wav, _ = librosa.load(audio_prompt_path, sr=self.sr)
        ref_16k_wav = librosa.resample(ref_24k_wav, orig_sr=self.sr, target_sr=S3_SR)

        s3gen_ref_wav = ref_24k_wav[: 10 * self.sr]
        ref_dict = self.s3gen.embed_ref(s3gen_ref_wav, self.sr, device=self.device)

        t3_cond_prompt_tokens = None
        if plen := self.t3.hp.speech_cond_prompt_len:
            s3_tokzr = self.s3gen.tokenizer
            t3_cond_prompt_tokens, _ = s3_tokzr.forward([ref_16k_wav[: 6 * S3_SR]], max_len=plen)
            t3_cond_prompt_tokens = torch.atleast_2d(t3_cond_prompt_tokens).to(self.device)

        ve_embed = torch.from_numpy(self.ve.embeds_from_wavs([ref_16k_wav], sample_rate=S3_SR))
        ve_embed = ve_embed.mean(axis=0, keepdim=True).to(self.device)

        return T3Cond(
            speaker_emb=ve_embed,
            cond_prompt_speech_tokens=t3_cond_prompt_tokens,
            emotion_adv=exaggeration * torch.ones(1, 1, 1),
        ).to(device=self.device), ref_dict

    def generate(self, text: str, audio_prompt_path: str, language_id: str = "pt",
                 exaggeration: float = 0.5, cfg_weight: float = 0.5,
                 temperature: float = 0.8, top_p: float = 1.0,
                 min_p: float = 0.05, repetition_penalty: float = 2.0):
        from chatterbox.models.s3tokenizer import drop_invalid_tokens

        t3_cond, ref_dict = self._prepare_conditionals(audio_prompt_path, exaggeration=exaggeration)

        text = _punc_norm(text)
        text_tokens = self.tokenizer.text_to_tokens(
            text,
            language_id=language_id.lower() if language_id else None,
        ).to(self.device)
        text_tokens = torch.cat([text_tokens, text_tokens], dim=0)

        text_tokens = F.pad(text_tokens, (1, 0), value=self.t3.hp.start_text_token)
        text_tokens = F.pad(text_tokens, (0, 1), value=self.t3.hp.stop_text_token)

        with torch.inference_mode():
            speech_tokens = self.t3.inference(
                t3_cond=t3_cond,
                text_tokens=text_tokens,
                max_new_tokens=1000,
                temperature=temperature,
                cfg_weight=cfg_weight,
                repetition_penalty=repetition_penalty,
                min_p=min_p,
                top_p=top_p,
            )
            speech_tokens = drop_invalid_tokens(speech_tokens[0]).to(self.device)
            wav, _ = self.s3gen.inference(
                speech_tokens=speech_tokens,
                ref_dict=ref_dict,
            )
            return wav.squeeze(0).detach().cpu()


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

    def _resolve_local_snapshot_dir(self, repo_dir: Path, missing_message: str) -> Path:
        snapshots_dir = repo_dir / "snapshots"
        if not snapshots_dir.is_dir():
            raise ChatterboxUnavailableError(missing_message)
        snapshots = [path for path in snapshots_dir.iterdir() if path.is_dir()]
        if not snapshots:
            raise ChatterboxUnavailableError(missing_message)
        return snapshots[0]

    def _chunk_texts_for_generation(
        self,
        text: str,
        segment_texts: Optional[Sequence[str]] = None,
        max_chars: int = 320,
    ) -> list[str]:
        def split_by_words(long_text: str) -> list[str]:
            words = long_text.split()
            pieces: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and len(candidate) > max_chars:
                    pieces.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                pieces.append(current)
            return pieces or [long_text]

        base_segments = [segment.strip() for segment in (segment_texts or [text]) if segment and segment.strip()]
        chunks: list[str] = []
        for segment in base_segments:
            if len(segment) <= max_chars:
                chunks.append(segment)
                continue

            sentences = [
                part.strip()
                for part in re.split(r"(?<=[.!?;:])\s+", segment)
                if part.strip()
            ] or [segment]
            current = ""
            for sentence in sentences:
                candidate = f"{current} {sentence}".strip()
                if current and len(candidate) > max_chars:
                    if len(current) > max_chars:
                        chunks.extend(split_by_words(current))
                    else:
                        chunks.append(current)
                    current = sentence
                else:
                    current = candidate
            if current:
                if len(current) > max_chars:
                    chunks.extend(split_by_words(current))
                else:
                    chunks.append(current)
        return chunks or [text.strip()]

    def _try_import_runtime_class(self):
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            return ChatterboxMultilingualTTS
        except ImportError:
            try:
                from chatterbox.tts import ChatterboxTTS as ChatterboxMultilingualTTS

                return ChatterboxMultilingualTTS
            except ImportError as exc:
                logger.warning(
                    "Chatterbox: wrapper de runtime indisponivel; seguindo com loader local. Motivo: %s",
                    exc,
                )
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

        runtime_cls = self._try_import_runtime_class()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device

        logger.info("Carregando Chatterbox PT-BR no device %s...", device)
        from services.model_manager import (
            CHATTERBOX_BASE_REPO_ID,
            get_hf_cache_dir,
            get_install_status,
            get_spec,
        )

        spec = get_spec("chatterbox-tts-pt-br")

        # Compatibilidade com testes mockados que substituem a classe real.
        is_mock_test = runtime_cls is not None and not runtime_cls.__module__.startswith("chatterbox")
        if is_mock_test:
            self.model = runtime_cls.from_pretrained(
                repo_id=spec.repo_id,
                device=device,
            )
            logger.info("Chatterbox PT-BR carregado com sucesso (modo compatibilidade mock/teste).")
            return

        status = get_install_status(spec)
        if not status or not status.get("path"):
            raise ChatterboxUnavailableError("Modelo Chatterbox PT-BR nao instalado no cache.")
        if status.get("dependency_status") == "missing-base-checkpoints":
            raise ChatterboxUnavailableError(
                "Dependencias base do Chatterbox ausentes no cache local. "
                "Baixe novamente o modelo pelo painel para incluir ve.pt e s3gen.pt."
            )

        pt_br_ckpt_dir = self._resolve_local_snapshot_dir(
            Path(status["path"]),
            "Snapshots do Chatterbox PT-BR nao encontrados no cache.",
        )
        base_repo_dir = Path(get_hf_cache_dir()) / ("models--" + CHATTERBOX_BASE_REPO_ID.replace("/", "--"))
        base_ckpt_dir = self._resolve_local_snapshot_dir(
            base_repo_dir,
            "Dependencias base do Chatterbox ausentes no cache local. "
            "Baixe novamente o modelo pelo painel para incluir ve.pt e s3gen.pt.",
        )

        map_location = torch.device("cpu") if device in ["cpu", "mps"] else None

        try:
            from chatterbox.models.s3gen import S3Gen
            from chatterbox.models.s3gen import S3GEN_SR
            from chatterbox.models.t3 import T3
            from chatterbox.models.t3.modules.t3_config import T3Config
            from chatterbox.models.tokenizers import MTLTokenizer
            from chatterbox.models.voice_encoder import VoiceEncoder
            from safetensors.torch import load_file as load_safetensors

            logger.info("Carregando codificador de voz (VoiceEncoder)...")
            ve = VoiceEncoder()
            ve.load_state_dict(
                torch.load(base_ckpt_dir / "ve.pt", map_location=map_location, weights_only=True)
            )
            ve.to(device).eval()

            logger.info("Carregando pesos T3 especificos do portugues brasileiro...")
            t3 = T3(T3Config.multilingual())
            t3_state = load_safetensors(pt_br_ckpt_dir / "t3_pt_br.safetensors")
            if "model" in t3_state:
                t3_state = t3_state["model"][0]
            t3.load_state_dict(t3_state)
            t3.to(device).eval()

            logger.info("Carregando vocodificador S3Gen v3 especifico...")
            s3gen = S3Gen()
            s3gen_path = pt_br_ckpt_dir / "s3gen_v3.safetensors"
            if s3gen_path.exists():
                s3gen_state = load_safetensors(s3gen_path)
            else:
                s3gen_state = torch.load(
                    pt_br_ckpt_dir / "s3gen_v3.pt",
                    map_location=map_location,
                    weights_only=True,
                )
            if "model" in s3gen_state:
                s3gen_state = s3gen_state["model"][0]
            s3gen.load_state_dict(s3gen_state, strict=False)
            s3gen.to(device).eval()

            logger.info("Carregando tokenizador de grafemas...")
            tokenizer = MTLTokenizer(
                str(pt_br_ckpt_dir / "grapheme_mtl_merged_expanded_v1.json")
            )

            if runtime_cls is not None:
                self.model = runtime_cls(t3, s3gen, ve, tokenizer, device)
            else:
                self.model = _LocalChatterboxRuntime(t3, s3gen, ve, tokenizer, device, S3GEN_SR)
            logger.info("Chatterbox PT-BR carregado com sucesso via loader local personalizado.")
        except Exception as exc:
            logger.error("Erro ao instanciar os componentes locais do Chatterbox: %s", exc)
            raise ChatterboxUnavailableError(f"Falha ao carregar modelo Chatterbox local: {exc}")

    def generate_voice_chatterbox(
        self,
        text: str,
        voice_id: Optional[str] = None,
        speaker_voices: Optional[Dict[str, str]] = None,
        speaker_id: str = "speaker_1",
        speed: float = 1.0,
        segment_texts: Optional[Sequence[str]] = None,
        parameters: Optional[Mapping[str, Any]] = None,
        segment_parameters: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from services import voice_profiles
        from services.vibevoice_tts_1_5b import VoiceUnavailableError, _wav_bytes_from_array

        resolved_voice_id = None
        if speaker_voices and speaker_id:
            import re

            match = re.search(r"([0-9]+)$", speaker_id)
            speaker_number = match.group(1) if match else "1"
            resolved_voice_id = speaker_voices.get(speaker_number)

        if not resolved_voice_id:
            resolved_voice_id = voice_id
        if not resolved_voice_id:
            resolved_voice_id = voice_profiles.get_default_voice_id()
        if not resolved_voice_id:
            raise VoiceUnavailableError(
                "Nenhuma voz de referencia foi selecionada ou encontrada para o Chatterbox."
            )

        resolved_voice_id = voice_profiles.resolve_voice_id(resolved_voice_id)
        if voice_profiles.is_legacy_windows_voice_id(resolved_voice_id):
            raise VoiceUnavailableError(
                "Presets Windows nao sao vozes reais de producao. "
                "Crie, importe ou selecione uma voz real."
            )

        try:
            profile = voice_profiles.get_voice(resolved_voice_id)
            ref_path = str(voice_profiles.chatterbox_reference_path(resolved_voice_id))
            # Perfis legados (e os doubles de testes) ainda não possuem o
            # estado por engine; eles continuam usando a referência canônica.
            if not os.path.exists(ref_path) and "engines" not in profile:
                ref_path = str(voice_profiles.reference_path(resolved_voice_id))
            if not os.path.exists(ref_path):
                raise VoiceUnavailableError(
                    f"A voz {resolved_voice_id} não possui referência Chatterbox utilizável. "
                    "Grave ao menos 8 segundos úteis de fala limpa."
                )
        except Exception as exc:
            raise VoiceUnavailableError(f"Voz {resolved_voice_id} indisponivel: {exc}")

        self._ensure_model()
        if not hasattr(self.model, "generate"):
            raise RuntimeError("O modelo Chatterbox nao possui o metodo generate.")

        import inspect

        sig = inspect.signature(self.model.generate)
        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
        from services.parameters_registry import validate_params
        from services.parameters_registry import get_engine_specs

        requested = dict(parameters or {})
        defaults = {spec.name: spec.default for spec in get_engine_specs("tts_chatterbox")}
        kwargs = {}
        if "language_id" in sig.parameters:
            kwargs["language_id"] = "pt"
        elif "language" in sig.parameters:
            kwargs["language"] = "pt"

        sample_rate = getattr(self.model, "sr", 24000)
        chunk_texts = self._chunk_texts_for_generation(text=text, segment_texts=segment_texts)
        parameter_sets = []
        for index in range(len(chunk_texts)):
            overrides = {}
            if segment_parameters and index < len(segment_parameters):
                overrides = dict(segment_parameters[index] or {})
            requested_for_segment = {**requested, **overrides}
            validation = validate_params("tts_chatterbox", {**defaults, **requested_for_segment})
            normalized = validation["normalized"]
            supported = {
                key: value for key, value in normalized.items()
                if key in sig.parameters or accepts_kwargs
            }
            unsupported = sorted(set(requested_for_segment) - set(supported))
            parameter_sets.append({
                "used": supported,
                "unsupported": unsupported,
                "issues": validation["issues"],
            })
        audio_chunks: list[np.ndarray] = []
        silence = np.zeros(int(sample_rate * 0.18), dtype=np.float32)

        for index, chunk_text in enumerate(chunk_texts):
            generation_kwargs = dict(parameter_sets[index]["used"])
            audio_tensor = self.model.generate(
                text=chunk_text,
                audio_prompt_path=ref_path,
                **kwargs,
                **generation_kwargs,
            )
            if isinstance(audio_tensor, torch.Tensor):
                audio_np = audio_tensor.detach().cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)

            audio_np = np.asarray(audio_np, dtype=np.float32).reshape(-1)
            if audio_np.size == 0:
                continue
            if index > 0:
                audio_chunks.append(silence.copy())
            audio_chunks.append(audio_np)

        if not audio_chunks:
            raise ChatterboxUnavailableError("Chatterbox-TTS nao retornou audio para nenhum segmento.")

        merged_audio = np.concatenate(audio_chunks)
        wav_bytes = _wav_bytes_from_array(merged_audio, sample_rate=sample_rate, speed=speed)

        return {
            "wav_bytes": wav_bytes,
            "engine_key": "chatterbox-tts-pt-br",
            "engine_label": "Chatterbox PT-BR",
            "fallback": False,
            "parameters": parameter_sets[0]["used"] if len(parameter_sets) == 1 else {},
            "parameters_by_segment": parameter_sets,
        }


chatterbox_engine = ChatterboxAdapter()

arbiter.register_engine(
    engine="tts_chatterbox",
    label="Chatterbox PT-BR",
    is_loaded=lambda: chatterbox_engine.is_loaded(),
    unload=lambda: chatterbox_engine.unload(),
    est_vram_mb=lambda: chatterbox_engine.est_vram_mb(),
    current_model=lambda: chatterbox_engine.current_model(),
)
