from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from faster_whisper import WhisperModel

from app import config


def ensure_nltk_data() -> None:
    import nltk

    for find_path, package in [
        ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
        ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
        ("corpora/cmudict", "cmudict"),
    ]:
        try:
            nltk.data.find(find_path)
        except LookupError:
            try:
                nltk.download(package, quiet=True)
            except Exception:  # noqa: BLE001, S110
                # One of these two resource names doesn't exist for the
                # installed nltk version; that failure is expected, not a bug.
                pass


def load_g2p():
    ensure_nltk_data()
    from g2p_en import G2p

    return G2p()


def load_whisper_model() -> WhisperModel:
    return WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device="cpu",
        compute_type=config.WHISPER_COMPUTE_TYPE,
        download_root=str(config.WHISPER_MODEL_DIR),
    )


def transcribe_audio(model: WhisperModel, audio_path: Path) -> str:
    segments, _info = model.transcribe(
        str(audio_path),
        language="en",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def get_whisper_model(request: Request) -> WhisperModel:
    return request.app.state.whisper_model


def get_g2p(request: Request):
    return request.app.state.g2p


WhisperModelDep = Annotated[WhisperModel, Depends(get_whisper_model)]
G2pDep = Annotated[object, Depends(get_g2p)]
