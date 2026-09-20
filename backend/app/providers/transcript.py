from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptCue:
    start: float
    duration: float
    text: str


class TranscriptProvider(Protocol):
    """Abstraction for any source that can return timestamped transcript cues."""

    name: str

    def fetch(self, video_id: str) -> list[TranscriptCue]: ...
