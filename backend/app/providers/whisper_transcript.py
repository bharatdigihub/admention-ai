from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.exceptions import TranscriptUnavailableError
from app.providers.transcript import TranscriptCue, TranscriptProvider

logger = logging.getLogger(__name__)

SAMPLE_CUES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "whisper" / "sample.json"


class WhisperModel(Protocol):
    def transcribe(self, audio_path: str, **kwargs: Any) -> dict[str, Any]: ...


class WhisperTranscriptProvider:
    """Whisper fallback that shares the TranscriptProvider interface.

    Development defaults to a local timestamped sample (or mock). Production can
    point `WHISPER_PROVIDER=local` at a local Whisper install. No paid
    transcription service is required.
    """

    name = "whisper"

    def __init__(
        self,
        cues: list[TranscriptCue] | None = None,
        model: WhisperModel | None = None,
        sample_path: Path | None = None,
    ) -> None:
        self._cues = cues
        self._model = model
        self._sample_path = sample_path
        self._settings = get_settings()

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        if self._cues is not None:
            return list(self._cues)

        if not self._settings.whisper_enabled:
            raise TranscriptUnavailableError(
                "YouTube captions are unavailable and Whisper fallback is disabled."
            )

        provider = (self._settings.whisper_provider or "mock").lower()
        if provider == "mock":
            return self.load_sample_cues()
        if provider == "local":
            audio_path = self._sample_path or self._configured_sample_audio()
            if audio_path is None:
                raise TranscriptUnavailableError(
                    "Local Whisper is enabled but no sample audio file is configured."
                )
            return self.transcribe_file(audio_path)

        raise TranscriptUnavailableError(
            f"Unknown Whisper provider '{self._settings.whisper_provider}'."
        )

    def load_sample_cues(self, path: Path | None = None) -> list[TranscriptCue]:
        sample_path = path or SAMPLE_CUES_PATH
        if not sample_path.exists():
            raise TranscriptUnavailableError("The local Whisper sample is missing.")
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        cues = [
            TranscriptCue(start=float(item["start"]), duration=float(item["duration"]), text=str(item["text"]).strip())
            for item in payload
            if str(item.get("text", "")).strip()
        ]
        if not cues:
            raise TranscriptUnavailableError("The local Whisper sample was empty.")
        return cues

    def transcribe_file(self, audio_path: Path) -> list[TranscriptCue]:
        if not audio_path.exists():
            raise TranscriptUnavailableError("The Whisper audio sample was not found.")

        model = self._model
        if model is None:
            try:
                import whisper  # type: ignore[import-untyped]
            except ImportError as exc:
                raise TranscriptUnavailableError(
                    "Local Whisper is not installed. Install ffmpeg and `pip install openai-whisper`."
                ) from exc
            logger.info("Loading local Whisper model %s", self._settings.whisper_model)
            model = whisper.load_model(self._settings.whisper_model)

        result = model.transcribe(str(audio_path), verbose=False)
        cues: list[TranscriptCue] = []
        for segment in result.get("segments") or []:
            text = " ".join(str(segment.get("text") or "").split())
            if not text:
                continue
            start = float(segment.get("start") or 0.0)
            end = float(segment.get("end") or start)
            cues.append(TranscriptCue(start=start, duration=max(0.0, end - start), text=text))
        if not cues:
            raise TranscriptUnavailableError("Whisper returned no timestamped segments.")
        return cues

    def _configured_sample_audio(self) -> Path | None:
        raw = getattr(self._settings, "whisper_sample_path", "") or ""
        if not raw:
            return None
        return Path(raw)


def get_whisper_transcript_provider() -> TranscriptProvider:
    return WhisperTranscriptProvider()
