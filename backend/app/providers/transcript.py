from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

_IP_BLOCK_MARKERS = (
    "http 403",
    "http 429",
    "ipaddressblocked",
    "requestblocked",
    "ipblocked",
    "blocked this server",
    "blocked this host",
    "datacenter ip",
    "ip address blocked",
    "too many requests",
    "login_required",
    "signinconfirm",
)


@dataclass(frozen=True)
class TranscriptCue:
    start: float
    duration: float
    text: str


class TranscriptProvider(Protocol):
    """Abstraction for any source that can return timestamped transcript cues."""

    name: str

    def fetch(self, video_id: str) -> list[TranscriptCue]: ...


def is_youtube_ip_block(exc: object) -> bool:
    """True when YouTube refused the request because the caller looks like a datacenter."""
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in _IP_BLOCK_MARKERS)