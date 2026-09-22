from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from app.providers.transcript import TranscriptCue

_VTT_TS = re.compile(
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)
_VTT_TAG = re.compile(r"<[^>]+>")


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


def parse_webvtt(content: str) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines):
        match = _VTT_TS.search(lines[index])
        if not match:
            index += 1
            continue
        start = _vtt_timestamp(match, 0)
        end = _vtt_timestamp(match, 4)
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        text = _VTT_TAG.sub("", " ".join(text_lines))
        text = " ".join(text.replace("\n", " ").split())
        if text:
            cues.append(TranscriptCue(start=start, duration=max(0.0, end - start), text=text))
    return cues


def parse_ttml(content: str) -> list[TranscriptCue]:
    root = ET.fromstring(content)
    cues: list[TranscriptCue] = []
    for node in root.iter():
        if not str(node.tag).endswith("p"):
            continue
        begin = node.attrib.get("begin")
        if not begin:
            continue
        start = _parse_clock(begin)
        end_raw = node.attrib.get("end")
        end = _parse_clock(end_raw) if end_raw else start
        text = " ".join("".join(node.itertext()).replace("\n", " ").split())
        if text:
            cues.append(TranscriptCue(start=start, duration=max(0.0, end - start), text=text))
    return cues


def parse_caption_body(content: str) -> list[TranscriptCue]:
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        payload = json.loads(content)
        if isinstance(payload, dict):
            return parse_json3_captions(payload)
        return []
    if stripped.startswith("WEBVTT") or _VTT_TS.search("\n".join(stripped.splitlines()[:12])):
        return parse_webvtt(content)
    if stripped.startswith("<"):
        try:
            cues = parse_timedtext_xml(content)
        except ET.ParseError:
            cues = []
        if cues:
            return cues
        try:
            return parse_ttml(content)
        except ET.ParseError:
            return []
    return []


def _vtt_timestamp(match: re.Match[str], offset: int) -> float:
    hours = int(match.group(offset + 1) or 0)
    minutes = int(match.group(offset + 2) or 0)
    seconds = int(match.group(offset + 3) or 0)
    fraction = match.group(offset + 4) or "0"
    millis = int(fraction.ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def _parse_clock(value: str) -> float:
    raw = value.strip().lower().replace(",", ".")
    if raw.endswith("ms"):
        return float(raw[:-2]) / 1000.0
    if raw.endswith("s") and ":" not in raw:
        return float(raw[:-1])
    parts = raw.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(raw)
