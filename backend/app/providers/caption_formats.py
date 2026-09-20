from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from app.providers.transcript import TranscriptCue


def parse_json3_captions(payload: dict) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    for event in payload.get("events") or []:
        text = "".join(seg.get("utf8") or "" for seg in event.get("segs") or [])
        text = " ".join(text.replace("\n", " ").split())
        if not text:
            continue
        cues.append(
            TranscriptCue(
                start=float(event.get("tStartMs") or 0) / 1000.0,
                duration=float(event.get("dDurationMs") or 0) / 1000.0,
                text=text,
            )
        )
    return cues


def parse_timedtext_xml(content: str) -> list[TranscriptCue]:
    root = ET.fromstring(content)
    cues: list[TranscriptCue] = []
    for node in root.iter("text"):
        text = " ".join("".join(node.itertext()).replace("\n", " ").split())
        if not text:
            continue
        cues.append(
            TranscriptCue(
                start=float(node.attrib.get("start") or 0),
                duration=float(node.attrib.get("dur") or 0),
                text=text,
            )
        )
    return cues


def parse_caption_body(content: str) -> list[TranscriptCue]:
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        payload = json.loads(content)
        if isinstance(payload, dict):
            return parse_json3_captions(payload)
        return []
    if stripped.startswith("<"):
        return parse_timedtext_xml(content)
    return []
