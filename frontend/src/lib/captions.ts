export type CaptionCue = {
  start: number;
  duration: number;
  text: string;
};

const INVIDIOUS_BASES = ["https://inv.nadeko.net"];
const PIPED_BASES = [
  "https://api.piped.private.coffee",
  "https://pipedapi.r4fo.com",
  "https://pipedapi.leptons.xyz",
  "https://pipedapi.smnz.de",
];

const VTT_TS =
  /(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})/;

export function parseWebVtt(content: string): CaptionCue[] {
  const cues: CaptionCue[] = [];
  const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(VTT_TS);
    if (!match) {
      continue;
    }
    const start = vttTimestamp(match, 1);
    const end = vttTimestamp(match, 5);
    const textLines: string[] = [];
    index += 1;
    while (index < lines.length && lines[index].trim()) {
      textLines.push(lines[index]);
      index += 1;
    }
    const text = textLines
      .join(" ")
      .replace(/<[^>]+>/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (text) {
      cues.push({ start, duration: Math.max(0, end - start), text });
    }
  }
  return cues;
}

export function parseJson3Captions(payload: { events?: Array<{ tStartMs?: number; dDurationMs?: number; segs?: Array<{ utf8?: string }> }> }): CaptionCue[] {
  const cues: CaptionCue[] = [];
  for (const event of payload.events || []) {
    const text = (event.segs || [])
      .map((seg) => seg.utf8 || "")
      .join("")
      .replace(/\n/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!text) {
      continue;
    }
    cues.push({
      start: (event.tStartMs || 0) / 1000,
      duration: (event.dDurationMs || 0) / 1000,
      text,
    });
  }
  return cues;
}

export async function fetchMirrorCues(videoId: string): Promise<CaptionCue[]> {
  try {
    const cues = await fetchHostingerProxy(videoId);
    if (cues.length) {
      return cues;
    }
  } catch {
    // Hostinger PHP proxy is optional; continue to public mirrors.
  }
  for (const base of INVIDIOUS_BASES) {
    try {
      const cues = await fetchInvidious(base, videoId);
      if (cues.length) {
        return cues;
      }
    } catch {
      // Try the next public caption host.
    }
  }
  for (const base of PIPED_BASES) {
    try {
      const cues = await fetchPiped(base, videoId);
      if (cues.length) {
        return cues;
      }
    } catch {
      // Try the next public caption host.
    }
  }
  throw new Error("Could not load captions from a public caption mirror.");
}

async function fetchHostingerProxy(videoId: string): Promise<CaptionCue[]> {
  const response = await fetch(`/caption-proxy.php?v=${encodeURIComponent(videoId)}`);
  if (!response.ok) {
    throw new Error(`Caption proxy HTTP ${response.status}`);
  }
  const payload = await response.json();
  const segments = Array.isArray(payload?.segments) ? payload.segments : [];
  return segments
    .map((item: { start?: number; duration?: number; text?: string }) => ({
      start: Number(item.start) || 0,
      duration: Number(item.duration) || 0,
      text: String(item.text || "").trim(),
    }))
    .filter((item: CaptionCue) => item.text);
}

async function fetchInvidious(base: string, videoId: string): Promise<CaptionCue[]> {
  const listing = await fetchJson(`${base}/api/v1/captions/${videoId}`);
  const tracks = Array.isArray(listing.captions) ? listing.captions : [];
  const ranked = rankTracks(tracks);
  for (const track of ranked) {
    const url = absoluteUrl(base, track.url || `/api/v1/captions/${videoId}?label=${encodeURIComponent(track.label || "")}`);
    const response = await fetch(url);
    if (!response.ok) {
      continue;
    }
    const body = await response.text();
    const cues = body.trim().startsWith("{") ? parseJson3Captions(JSON.parse(body)) : parseWebVtt(body);
    if (cues.length) {
      return cues;
    }
  }
  return [];
}

async function fetchPiped(base: string, videoId: string): Promise<CaptionCue[]> {
  const payload = await fetchJson(`${base}/streams/${videoId}`);
  const tracks = Array.isArray(payload.subtitles) ? payload.subtitles : [];
  for (const track of rankTracks(tracks)) {
    if (!track.url) {
      continue;
    }
    for (const fmt of ["json3", "vtt"]) {
      const response = await fetch(withFmt(track.url, fmt));
      if (!response.ok) {
        continue;
      }
      const body = await response.text();
      const cues = body.trim().startsWith("{") ? parseJson3Captions(JSON.parse(body)) : parseWebVtt(body);
      if (cues.length) {
        return cues;
      }
    }
  }
  return [];
}

async function fetchJson(url: string): Promise<Record<string, any>> {
  const response = await fetch(url);
  let payload: Record<string, any> | null = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const blocked = hostBlockReason(payload);
  if (blocked) {
    throw new Error(blocked);
  }
  if (!response.ok) {
    throw new Error(`Caption mirror HTTP ${response.status}`);
  }
  if (!payload || typeof payload !== "object") {
    throw new Error("Caption mirror returned a non-JSON body.");
  }
  return payload;
}

function hostBlockReason(payload: Record<string, any> | null): string | null {
  if (!payload) {
    return null;
  }
  if (payload.subtitles || payload.captions || payload.events) {
    return null;
  }
  const blob = `${payload.error || ""} ${payload.message || ""} ${payload.errorMessage || ""}`;
  const lower = blob.toLowerCase();
  if (
    lower.includes("login_required") ||
    lower.includes("not a bot") ||
    lower.includes("signinconfirm") ||
    lower.includes("confirm that you're not a bot")
  ) {
    return "YouTube bot-check blocked this caption host.";
  }
  if (payload.error || payload.message) {
    const message = String(payload.message || payload.error).split("\n")[0];
    if (message.includes("org.schabi") || message.includes("at org.")) {
      return "YouTube bot-check blocked this caption host.";
    }
    return message.slice(0, 180);
  }
  return null;
}

function rankTracks(tracks: Array<Record<string, any>>): Array<Record<string, any>> {
  return [...tracks].sort((left, right) => scoreTrack(left) - scoreTrack(right));
}

function scoreTrack(track: Record<string, any>): number {
  const label = String(track.label || track.name || "").toLowerCase();
  const lang = String(track.languageCode || track.code || track.lang || "").toLowerCase();
  const auto = Boolean(track.autoGenerated) || label.includes("auto");
  if (lang === "en" || lang.startsWith("en-") || label.startsWith("english")) {
    return auto ? 1 : 0;
  }
  if (lang.startsWith("en") || label.includes("english")) {
    return auto ? 3 : 2;
  }
  return 4;
}

function absoluteUrl(base: string, url: string): string {
  if (!url) {
    return base;
  }
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return `${base.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

function withFmt(url: string, fmt: string): string {
  const parsed = new URL(url);
  parsed.searchParams.set("fmt", fmt);
  return parsed.toString();
}

function vttTimestamp(match: RegExpMatchArray, offset: number): number {
  const hours = Number(match[offset] || 0);
  const minutes = Number(match[offset + 1] || 0);
  const seconds = Number(match[offset + 2] || 0);
  const millis = Number((match[offset + 3] || "0").padEnd(3, "0").slice(0, 3));
  return hours * 3600 + minutes * 60 + seconds + millis / 1000;
}
