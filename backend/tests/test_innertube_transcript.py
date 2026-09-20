import httpx
import pytest

from app.core.exceptions import TranscriptUnavailableError
from app.providers.caption_formats import parse_caption_body, parse_json3_captions
from app.providers.innertube_transcript import (
    InnertubeTranscriptProvider,
    find_transcript_params,
    find_visitor_data,
    parse_get_transcript_cues,
)


def test_parse_json3_caption_events() -> None:
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


def test_parse_timedtext_xml() -> None:
    cues = parse_caption_body(
        '<transcript><text start="12.5" dur="1.5">Feldman Automotive</text></transcript>'
    )
    assert len(cues) == 1
    assert cues[0].start == 12.5
    assert cues[0].duration == 1.5
    assert cues[0].text == "Feldman Automotive"


def test_innertube_fetches_english_json3_track() -> None:
    player = {
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [
                    {"languageCode": "hi", "baseUrl": "https://example.test/hi"},
                    {"languageCode": "en", "baseUrl": "https://example.test/en"},
                ]
            }
        }
    }
    captions = {
        "events": [
            {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Hello from InnerTube"}]}
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/player"):
            return httpx.Response(200, json=player)
        if "fmt=json3" in str(request.url) and "/en" in str(request.url):
            return httpx.Response(200, json=captions)
        return httpx.Response(404, text="missing")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cues = InnertubeTranscriptProvider(client=client).fetch("dQw4w9WgXcQ")
    assert cues[0].text == "Hello from InnerTube"
    assert cues[0].start == 1.0


def test_innertube_unavailable_without_tracks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"playabilityStatus": {"status": "OK"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TranscriptUnavailableError):
        InnertubeTranscriptProvider(client=client).fetch("dQw4w9WgXcQ")


def test_find_transcript_params() -> None:
    params = find_transcript_params(
        {
            "engagementPanels": [
                {
                    "continuationEndpoint": {
                        "getTranscriptEndpoint": {"params": "abc123"},
                    }
                }
            ]
        }
    )
    assert params == "abc123"


def test_find_visitor_data() -> None:
    visitor = find_visitor_data({"responseContext": {"visitorData": "CgtVisitor"}})
    assert visitor == "CgtVisitor"


def test_parse_get_transcript_cues() -> None:
    cues = parse_get_transcript_cues(
        {
            "actions": [
                {
                    "transcriptSegmentRenderer": {
                        "startMs": "1500",
                        "endMs": "2500",
                        "snippet": {"runs": [{"text": "InnerTube next"}]},
                    }
                }
            ]
        }
    )
    assert len(cues) == 1
    assert cues[0].start == 1.5
    assert cues[0].duration == 1.0
    assert cues[0].text == "InnerTube next"


def test_innertube_uses_get_transcript_when_next_has_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/next"):
            return httpx.Response(
                200,
                json={"engagementPanels": [{"getTranscriptEndpoint": {"params": "p1"}}]},
            )
        if request.url.path.endswith("/get_transcript"):
            return httpx.Response(
                200,
                json={
                    "actions": [
                        {
                            "transcriptSegmentRenderer": {
                                "startMs": "0",
                                "endMs": "1200",
                                "snippet": {"runs": [{"text": "From get_transcript"}]},
                            }
                        }
                    ]
                },
            )
        return httpx.Response(500, text="should not hit player")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cues = InnertubeTranscriptProvider(client=client).fetch("dQw4w9WgXcQ")
    assert cues[0].text == "From get_transcript"
