from app.providers.ytdlp_transcript import YtDlpTranscriptProvider


def test_ytdlp_parses_json3_caption_events() -> None:
    provider = YtDlpTranscriptProvider()
    cues = provider._parse_json3(
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
