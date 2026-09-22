from app.core.exceptions import TranscriptUnavailableError
from app.providers.hostinger_proxy import HostingerCaptionProxyProvider
from app.providers.transcript import TranscriptCue
import httpx


def test_hostinger_proxy_parses_segments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("v") == "TBNIzzvZpG4"
        assert "Chrome" in request.headers.get("user-agent", "")
        return httpx.Response(
            200,
            json={"segments": [{"start": 1.5, "duration": 2.0, "text": "Hello from Hostinger"}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cues = HostingerCaptionProxyProvider(
        client=client,
        proxy_url="https://adverify.codewithbharat.dev/caption-proxy.php",
    ).fetch("TBNIzzvZpG4")
    assert cues == [TranscriptCue(start=1.5, duration=2.0, text="Hello from Hostinger")]


def test_hostinger_proxy_requires_url() -> None:
    try:
        HostingerCaptionProxyProvider(proxy_url="").fetch("TBNIzzvZpG4")
        assert False, "expected failure"
    except TranscriptUnavailableError as exc:
        assert "not configured" in str(exc)


def test_hostinger_proxy_maps_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "YouTube captions could not be loaded from this host."})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        HostingerCaptionProxyProvider(client=client, proxy_url="https://example.test/caption-proxy.php").fetch("TBNIzzvZpG4")
        assert False, "expected failure"
    except TranscriptUnavailableError as exc:
        assert "502" in str(exc)
        assert "could not be loaded" in str(exc)
