import json
from pathlib import Path

from app.core.exceptions import TranscriptUnavailableError
from app.providers.transcript import TranscriptCue


class LocalFixtureTranscriptProvider:
    """Loads timestamped cues from a local JSON fixture when YouTube captions fail.

    Used for local development when YouTube blocks transcript requests.
    """

    name = "fixture"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        path = self.fixtures_dir / f"{video_id}.json"
        if not path.exists():
            raise TranscriptUnavailableError("No local transcript fixture is available for this video.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        cues = [
            TranscriptCue(
                start=float(item["start"]),
                duration=float(item["duration"]),
                text=str(item["text"]),
            )
            for item in payload
        ]
        if not cues:
            raise TranscriptUnavailableError("The local transcript fixture was empty.")
        return cues
