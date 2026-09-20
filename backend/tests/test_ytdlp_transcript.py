from app.providers.caption_formats import parse_json3_captions
from app.providers.ytdlp_transcript import YtDlpTranscriptProvider


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
