import httpx
import pytest

from app.core.exceptions import TranscriptUnavailableError
from app.providers.caption_formats import parse_json3_captions
from app.providers.transcript import TranscriptCue
from app.providers.ytdlp_transcript import YtDlpTranscriptProvider, _PLAYER_CLIENT_ATTEMPTS


def test_ytdlp_parses_json3_caption_events() -> None:
    cues = parse_json3_captions(
        {
            "events": [
                {"tStartMs": 43000, "dDurationMs": 2120, "segs": [{"utf8": "Never gonna give you up"}]},
                {"tStartMs": 1000, "dDurationMs": 500, "segs": [{"utf8": "\n"}]},
            ]
        }
    )
    assert len(cues) == 1
    assert cues[0].start == 43.0
    assert cues[0].duration == 2.12
    assert cues[0].text == "Never gonna give you up"


def test_ytdlp_picks_any_language_json3_track() -> None:
    provider = YtDlpTranscriptProvider()
    track = provider._pick_english_track(
        {
            "hi": [{"ext": "json3", "url": "https://example.test/hi"}],
        }
    )
    assert track is not None
    assert track["url"] == "https://example.test/hi"


def test_ytdlp_multiple_player_client_attempts_defined() -> None:
    """Verify the multi-client fallback list has at least 3 options."""
    assert len(_PLAYER_CLIENT_ATTEMPTS) >= 3
    assert ["ios"] in _PLAYER_CLIENT_ATTEMPTS
    assert ["android"] in _PLAYER_CLIENT_ATTEMPTS
    assert ["tv_embedded"] in _PLAYER_CLIENT_ATTEMPTS


def test_ytdlp_fetch_succeeds_via_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider succeeds when _caption_url returns a URL and the HTTP client returns valid JSON."""
    caption_data = {
        "events": [
            {"tStartMs": 5000, "dDurationMs": 1500, "segs": [{"utf8": "Test caption"}]}
        ]
    }

    def fake_caption_url(self, video_id: str, player_clients: list) -> str:
        return "https://example.test/captions.json"

    monkeypatch.setattr(YtDlpTranscriptProvider, "_caption_url", fake_caption_url)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=caption_data)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = YtDlpTranscriptProvider(client=client)
    cues = provider.fetch("dQw4w9WgXcQ")

    assert len(cues) == 1
    assert cues[0].start == 5.0
    assert cues[0].text == "Test caption"


def test_ytdlp_raises_unavailable_when_caption_url_always_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider raises TranscriptUnavailableError when all player client attempts fail."""
    call_count = 0

    def fake_caption_url(self, video_id: str, player_clients: list) -> str:
        nonlocal call_count
        call_count += 1
        raise TranscriptUnavailableError(f"no captions for client={player_clients}")

    monkeypatch.setattr(YtDlpTranscriptProvider, "_caption_url", fake_caption_url)

    provider = YtDlpTranscriptProvider()
    with pytest.raises(TranscriptUnavailableError) as exc_info:
        provider.fetch("dQw4w9WgXcQ")

    # Must have tried all configured player clients
    assert call_count == len(_PLAYER_CLIENT_ATTEMPTS)
    assert "TranscriptUnavailableError" in str(exc_info.value) or "no captions" in str(exc_info.value)


def test_ytdlp_detects_403_ip_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider raises TranscriptUnavailableError with a clear IP-block message on HTTP 403."""

    def fake_caption_url(self, video_id: str, player_clients: list) -> str:
        return "https://example.test/captions.json"

    monkeypatch.setattr(YtDlpTranscriptProvider, "_caption_url", fake_caption_url)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = YtDlpTranscriptProvider(client=client)

    with pytest.raises(TranscriptUnavailableError) as exc_info:
        provider.fetch("dQw4w9WgXcQ")

    assert "403" in str(exc_info.value)
