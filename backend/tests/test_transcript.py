from types import SimpleNamespace
import wave
from pathlib import Path

import pytest

from app.core.exceptions import TranscriptUnavailableError
from app.models.video import Video
from app.providers.fixture_transcript import LocalFixtureTranscriptProvider
from app.providers.transcript import TranscriptCue
from app.providers.whisper_transcript import WhisperTranscriptProvider
from app.providers.youtube_transcript import YouTubeTranscriptProvider
from app.services.transcript import TranscriptService


class FakeProvider:
    def __init__(self, name: str, result: list[TranscriptCue] | Exception) -> None:
        self.name = name
        self._result = result
        self.calls = 0

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return list(self._result)


def _write_silence_wav(path: Path, duration_ms: int = 300) -> None:
    framerate = 8000
    nframes = int(framerate * duration_ms / 1000)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(framerate)
        handle.writeframes(b"\x00\x00" * nframes)


def _video(db) -> Video:
    video = Video(
        youtube_video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Test video",
        transcript_status="pending",
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def test_normalize_and_store_transcript_segments(db) -> None:
    video = _video(db)
    provider = FakeProvider(
        "youtube",
        [
            TranscriptCue(start=872.4, duration=4.2, text="  Today's show is sponsored by\nFeldman Automotive  "),
            TranscriptCue(start=880.0, duration=2.0, text="   "),
        ],
    )
    service = TranscriptService(db, providers=[provider])
    updated = service.ensure_transcript(video)
    segments = service.get_segments(video.youtube_video_id)

    assert updated.transcript_status == "available"
    assert len(segments) == 1
    assert segments[0].start_seconds == 872.4
    assert segments[0].duration_seconds == 4.2
    assert segments[0].text == "Today's show is sponsored by Feldman Automotive"

    payload = service.get_transcript(video.youtube_video_id)
    assert payload.segments[0].start == 872.4
    assert payload.segments[0].duration == 4.2


def test_skips_duplicate_transcript_processing(db) -> None:
    video = _video(db)
    provider = FakeProvider(
        "youtube",
        [TranscriptCue(start=1.0, duration=2.0, text="Hello")],
    )
    service = TranscriptService(db, providers=[provider])

    service.ensure_transcript(video)
    service.ensure_transcript(video)

    assert provider.calls == 1
    assert len(service.get_segments(video.youtube_video_id)) == 1


def test_unavailable_youtube_transcript(db) -> None:
    video = _video(db)
    service = TranscriptService(
        db,
        providers=[FakeProvider("youtube", TranscriptUnavailableError("no captions"))],
    )

    with pytest.raises(TranscriptUnavailableError):
        service.ensure_transcript(video)

    db.refresh(video)
    assert video.transcript_status == "unavailable"
    assert service.get_segments(video.youtube_video_id) == []


def test_empty_transcript_is_unavailable(db) -> None:
    video = _video(db)
    service = TranscriptService(db, providers=[FakeProvider("youtube", [])])

    with pytest.raises(TranscriptUnavailableError):
        service.ensure_transcript(video)

    db.refresh(video)
    assert video.transcript_status == "unavailable"


def test_whisper_fallback_when_youtube_missing(db) -> None:
    video = _video(db)
    whisper_cues = [TranscriptCue(start=14.0, duration=3.0, text="Thanks to Feldman Automotive")]
    service = TranscriptService(
        db,
        providers=[
            FakeProvider("youtube", TranscriptUnavailableError("no captions")),
            FakeProvider("whisper", whisper_cues),
        ],
    )

    updated = service.ensure_transcript(video)
    segments = service.get_segments(video.youtube_video_id)

    assert updated.transcript_status == "whisper"
    assert segments[0].start_seconds == 14.0
    assert segments[0].text == "Thanks to Feldman Automotive"


def test_local_fixture_fallback(db) -> None:
    video = _video(db)
    service = TranscriptService(
        db,
        providers=[
            FakeProvider("youtube", TranscriptUnavailableError("no captions")),
            LocalFixtureTranscriptProvider(),
        ],
    )
    updated = service.ensure_transcript(video)
    segments = service.get_segments(video.youtube_video_id)

    assert updated.transcript_status == "fixture"
    assert any("Never gonna give you up" in segment.text for segment in segments)


def test_whisper_provider_follows_transcript_interface() -> None:
    provider = WhisperTranscriptProvider(
        cues=[TranscriptCue(start=1.5, duration=2.0, text="Mock cue")]
    )
    cues = provider.fetch("abc12345678")
    assert provider.name == "whisper"
    assert cues[0].start == 1.5
    assert cues[0].text == "Mock cue"


def test_whisper_loads_short_local_sample() -> None:
    provider = WhisperTranscriptProvider()
    cues = provider.load_sample_cues()
    assert cues[0].start == 0.0
    assert cues[0].duration == 2.4
    assert cues[0].text == "This is a short local Whisper sample."
    assert cues[1].start == 2.4


def test_whisper_transcribes_local_audio_sample(tmp_path) -> None:
    audio_path = tmp_path / "sample.wav"
    _write_silence_wav(audio_path)

    class FakeModel:
        def transcribe(self, path: str, **kwargs):
            assert path == str(audio_path)
            return {
                "segments": [
                    {"start": 0.0, "end": 1.5, "text": "hello from whisper"},
                    {"start": 1.5, "end": 3.25, "text": "timestamp preserved"},
                ]
            }

    provider = WhisperTranscriptProvider(model=FakeModel())
    cues = provider.transcribe_file(audio_path)
    assert cues[0].start == 0.0
    assert cues[0].duration == 1.5
    assert cues[1].start == 1.5
    assert cues[1].duration == 1.75
    assert cues[1].text == "timestamp preserved"


def test_whisper_disabled_is_unavailable(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("WHISPER_ENABLED", "false")
    get_settings.cache_clear()
    try:
        provider = WhisperTranscriptProvider()
        with pytest.raises(TranscriptUnavailableError, match="disabled"):
            provider.fetch("dQw4w9WgXcQ")
    finally:
        get_settings.cache_clear()


def test_default_provider_chain_ends_with_whisper(db) -> None:
    service = TranscriptService(db)
    assert [provider.name for provider in service.providers] == [
        "youtube",
        "youtube",
        "fixture",
        "whisper",
    ]


def test_youtube_transcript_provider_preserves_timestamps() -> None:
    class FakeApi:
        def fetch(self, video_id: str, languages: tuple[str, ...]):
            assert video_id == "dQw4w9WgXcQ"
            return [
                SimpleNamespace(start=872.4, duration=4.2, text="Today's show is sponsored by Feldman Automotive"),
                SimpleNamespace(start=880.0, duration=1.5, text="Welcome back"),
            ]

    provider = YouTubeTranscriptProvider(api=FakeApi())
    cues = provider.fetch("dQw4w9WgXcQ")
    assert cues[0].start == 872.4
    assert cues[0].duration == 4.2
    assert cues[1].start == 880.0


def test_youtube_transcript_provider_maps_missing_captions() -> None:
    class BoomApi:
        def fetch(self, video_id: str, languages: tuple[str, ...]):
            raise RuntimeError("blocked")

    provider = YouTubeTranscriptProvider(api=BoomApi())
    with pytest.raises(TranscriptUnavailableError):
        provider.fetch("dQw4w9WgXcQ")
