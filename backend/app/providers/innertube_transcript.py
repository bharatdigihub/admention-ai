from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.exceptions import TranscriptUnavailableError
from app.core.proxy import build_httpx_client
from app.providers.caption_formats import parse_caption_body
from app.providers.transcript import TranscriptCue, TranscriptProvider, is_youtube_ip_block

logger = logging.getLogger(__name__)

YOUTUBEI = "https://www.youtube.com/youtubei/v1"

ANDROID_CLIENT = {
    "clientName": "ANDROID",
    "clientVersion": "19.44.38",
    "androidSdkVersion": 30,
    "osName": "Android",
    "osVersion": "14",
    "hl": "en",
    "gl": "US",
    "userAgent": "com.google.android.youtube/19.44.38 (Linux; U; Android 14) gzip",
    "clientNameId": "3",
}

WEB_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20250925.01.00",
    "hl": "en",
    "gl": "US",
    "userAgent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "clientNameId": "1",
}

IOS_CLIENT = {
    "clientName": "IOS",
    "clientVersion": "20.10.38",
    "deviceMake": "Apple",
    "deviceModel": "iPhone16,2",
    "osName": "iOS",
    "osVersion": "18.1.0",
    "hl": "en",
    "gl": "US",
    "userAgent": "com.google.ios.youtube/20.10.38 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)",
    "clientNameId": "5",
}

TV_EMBED_CLIENT = {
    "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
    "clientVersion": "2.0",
    "hl": "en",
    "gl": "US",
    "userAgent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version",
    "clientNameId": "85",
}

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

WEB_EMBEDDED_CLIENT = {
    "clientName": "WEB_EMBEDDED_PLAYER",
    "clientVersion": "1.20240920.01.00",
    "clientScreen": "EMBED",
    "hl": "en",
    "gl": "US",
    "userAgent": CHROME_UA,
    "clientNameId": "56",
}

PREFERRED_LANGS = ("en", "en-US", "en-GB", "en-orig", "a.en")


def find_transcript_params(node: object) -> str | None:
    if isinstance(node, dict):
        endpoint = node.get("getTranscriptEndpoint")
        if isinstance(endpoint, dict) and endpoint.get("params"):
            return str(endpoint["params"])
        for value in node.values():
            found = find_transcript_params(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_transcript_params(item)
            if found:
                return found
    return None


def find_visitor_data(node: object) -> str | None:
    if isinstance(node, dict):
        context = node.get("responseContext")
        if isinstance(context, dict) and context.get("visitorData"):
            return str(context["visitorData"])
        if node.get("visitorData"):
            return str(node["visitorData"])
        for value in node.values():
            found = find_visitor_data(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_visitor_data(item)
            if found:
                return found
    return None


def parse_get_transcript_cues(node: object) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            renderer = value.get("transcriptSegmentRenderer")
            if isinstance(renderer, dict):
                start_ms = float(renderer.get("startMs") or 0)
                end_ms = float(renderer.get("endMs") or start_ms)
                runs = ((renderer.get("snippet") or {}).get("runs") or [])
                text = " ".join("".join(run.get("text") or "" for run in runs).replace("\n", " ").split())
                if text:
                    cues.append(
                        TranscriptCue(
                            start=start_ms / 1000.0,
                            duration=max(0.0, (end_ms - start_ms) / 1000.0),
                            text=text,
                        )
                    )
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return cues


class InnertubeTranscriptProvider:
    """Fetches captions through YouTube InnerTube so cloud hosts can still read tracks."""

    name = "innertube"
    direct_youtube = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client
        self._visitor: str | None = None

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        client = self._client or build_httpx_client(timeout=25.0, follow_redirects=True)
        owns_client = self._client is None
        self._visitor = None
        try:
            cues = self._fetch_via_next(client, video_id)
            if cues:
                return cues
            tracks, player_client = self._caption_tracks(client, video_id)
            track = self._pick_track(tracks)
            if track is None:
                raise TranscriptUnavailableError(
                    "YouTube InnerTube did not return caption tracks for this video."
                )
            cues = self._download_cues(client, str(track["baseUrl"]), video_id, player_client)
        except TranscriptUnavailableError:
            raise
        except Exception as exc:
            logger.exception("InnerTube caption request failed for %s [%s]", video_id, type(exc).__name__)
            raise TranscriptUnavailableError(
                f"YouTube InnerTube request failed: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            if owns_client:
                client.close()

        if not cues:
            raise TranscriptUnavailableError("The YouTube transcript was empty.")
        return cues

    def _fetch_via_next(self, client: httpx.Client, video_id: str) -> list[TranscriptCue]:
        last_error: Exception | None = None
        for client_config in (ANDROID_CLIENT, IOS_CLIENT, WEB_CLIENT):
            try:
                next_body = self._post(
                    client,
                    f"{YOUTUBEI}/next?prettyPrint=false",
                    client_config,
                    {"videoId": video_id},
                    video_id,
                )
                self._remember_visitor(next_body)
                params = find_transcript_params(next_body)
                if not params:
                    logger.info(
                        "InnerTube %s next had no transcript params for %s",
                        client_config["clientName"],
                        video_id,
                    )
                    continue
                for transcript_client in (WEB_CLIENT, client_config):
                    transcript_body = self._post_transcript(
                        client, transcript_client, params, video_id
                    )
                    cues = parse_get_transcript_cues(transcript_body)
                    if cues:
                        logger.info(
                            "InnerTube get_transcript returned %s cues for %s via %s",
                            len(cues),
                            video_id,
                            transcript_client["clientName"],
                        )
                        return cues
            except TranscriptUnavailableError as exc:
                if is_youtube_ip_block(exc):
                    raise
                last_error = exc
                logger.info(
                    "InnerTube %s get_transcript path failed for %s [%s]: %s",
                    client_config["clientName"],
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                continue
            except Exception as exc:
                last_error = exc
                logger.info(
                    "InnerTube %s get_transcript path failed for %s [%s]: %s",
                    client_config["clientName"],
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                continue
        if last_error:
            logger.info(
                "InnerTube next/get_transcript exhausted for %s: [%s] %s",
                video_id,
                type(last_error).__name__,
                last_error,
            )
        return []

    def _post(
        self,
        client: httpx.Client,
        url: str,
        client_config: dict,
        extra: dict,
        video_id: str,
    ) -> dict:
        payload = self._player_payload(video_id, client_config)
        payload.update(extra)
        response = client.post(
            url,
            json=payload,
            headers=_headers(client_config, video_id, self._visitor),
        )
        # Log HTTP-level blocking signals explicitly so they appear in Render logs.
        if response.status_code in (403, 429):
            logger.warning(
                "YouTube returned HTTP %s for InnerTube %s request on %s — "
                "server IP may be blocked by YouTube (datacenter IP block).",
                response.status_code,
                client_config["clientName"],
                video_id,
            )
            raise TranscriptUnavailableError(
                f"YouTube blocked this server's IP address (HTTP {response.status_code}). "
                "This is a Render/cloud datacenter IP block, not a code bug."
            )
        response.raise_for_status()
        body = response.json()
        self._remember_visitor(body)
        return body

    def _post_transcript(
        self,
        client: httpx.Client,
        client_config: dict,
        params: str,
        video_id: str,
    ) -> dict:
        skip = {"userAgent", "clientNameId"}
        client_body = {key: value for key, value in client_config.items() if key not in skip}
        payload = {
            "context": {"client": client_body},
            "params": params,
        }
        response = client.post(
            f"{YOUTUBEI}/get_transcript?prettyPrint=false",
            json=payload,
            headers=_headers(client_config, video_id, self._visitor),
        )
        if response.status_code in (403, 429):
            logger.warning(
                "YouTube returned HTTP %s for get_transcript on %s — "
                "server IP may be blocked by YouTube.",
                response.status_code,
                video_id,
            )
            raise TranscriptUnavailableError(
                f"YouTube blocked this server's IP address (HTTP {response.status_code})."
            )
        response.raise_for_status()
        body = response.json()
        self._remember_visitor(body)
        return body

    def _remember_visitor(self, body: dict) -> None:
        visitor = find_visitor_data(body)
        if visitor:
            self._visitor = visitor

    def _caption_tracks(self, client: httpx.Client, video_id: str) -> tuple[list[dict], dict]:
        last_error: Exception | None = None
        last_status = None
        for client_config in (WEB_EMBEDDED_CLIENT, ANDROID_CLIENT, IOS_CLIENT, TV_EMBED_CLIENT):
            try:
                body = self._post(
                    client,
                    f"{YOUTUBEI}/player?prettyPrint=false",
                    client_config,
                    {},
                    video_id,
                )
                tracks = (
                    body.get("captions", {})
                    .get("playerCaptionsTracklistRenderer", {})
                    .get("captionTracks")
                    or []
                )
                if tracks:
                    logger.info(
                        "InnerTube %s returned %s caption tracks for %s",
                        client_config["clientName"],
                        len(tracks),
                        video_id,
                    )
                    return tracks, client_config
                last_status = (body.get("playabilityStatus") or {}).get("status")
                logger.info(
                    "InnerTube %s had no caption tracks for %s (playability=%s)",
                    client_config["clientName"],
                    video_id,
                    last_status,
                )
            except TranscriptUnavailableError as exc:
                if is_youtube_ip_block(exc):
                    raise
                last_error = exc
                logger.info(
                    "InnerTube %s player call blocked for %s: %s",
                    client_config["clientName"],
                    video_id,
                    exc,
                )
                continue
            except Exception as exc:
                last_error = exc
                logger.info(
                    "InnerTube %s player call failed for %s [%s]: %s",
                    client_config["clientName"],
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                continue
        if last_error:
            raise TranscriptUnavailableError(
                f"YouTube player API failed from this host: {type(last_error).__name__}: {last_error}"
            ) from last_error
        raise TranscriptUnavailableError(
            f"YouTube player API returned no caption tracks (playability={last_status})."
        )

    def _player_payload(self, video_id: str, client_config: dict) -> dict:
        skip = {"userAgent", "clientNameId"}
        client_body = {key: value for key, value in client_config.items() if key not in skip}
        payload: dict = {
            "context": {"client": client_body},
            "videoId": video_id,
            "contentCheckOk": True,
            "racyCheckOk": True,
        }
        if client_config["clientName"] in {"TVHTML5_SIMPLY_EMBEDDED_PLAYER", "WEB_EMBEDDED_PLAYER"}:
            payload["context"]["thirdParty"] = {"embedUrl": "https://www.youtube.com/"}
        return payload

    def _pick_track(self, tracks: list[dict]) -> dict | None:
        def lang_of(track: dict) -> str:
            return str(track.get("languageCode") or "").lower()

        for preferred in PREFERRED_LANGS:
            for track in tracks:
                if lang_of(track) == preferred.lower() and track.get("baseUrl"):
                    return track
        for track in tracks:
            if lang_of(track).startswith("en") and track.get("baseUrl"):
                return track
        for track in tracks:
            if track.get("baseUrl"):
                return track
        return None

    def _download_cues(
        self,
        client: httpx.Client,
        base_url: str,
        video_id: str,
        client_config: dict,
    ) -> list[TranscriptCue]:
        json_url = _with_fmt(base_url, "json3")
        response = client.get(json_url, headers=_headers(client_config, video_id, self._visitor))
        if response.status_code >= 400:
            raise TranscriptUnavailableError(
                f"YouTube caption file returned HTTP {response.status_code}."
            )
        cues = parse_caption_body(response.text)
        if cues:
            return cues
        xml_url = _with_fmt(base_url, "srv3")
        xml_response = client.get(xml_url, headers=_headers(client_config, video_id, self._visitor))
        if xml_response.status_code >= 400:
            raise TranscriptUnavailableError(
                f"YouTube caption file returned HTTP {xml_response.status_code}."
            )
        cues = parse_caption_body(xml_response.text)
        if not cues:
            raise TranscriptUnavailableError("YouTube caption file was empty.")
        return cues


def _headers(
    client_config: dict,
    video_id: str | None = None,
    visitor: str | None = None,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": client_config["userAgent"],
        "X-YouTube-Client-Name": client_config["clientNameId"],
        "X-YouTube-Client-Version": client_config["clientVersion"],
        "Origin": "https://www.youtube.com",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if video_id:
        headers["Referer"] = f"https://www.youtube.com/embed/{video_id}"
    if visitor:
        headers["X-Goog-Visitor-Id"] = visitor
    return headers


def _with_fmt(url: str, fmt: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "fmt"]
    query.append(("fmt", fmt))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def get_innertube_transcript_provider() -> TranscriptProvider:
    return InnertubeTranscriptProvider()
