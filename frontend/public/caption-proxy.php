<?php
/**
 * Same-origin caption proxy for Hostinger.
 *
 * Render's IP is blocked by YouTube. This script runs on Hostinger and fetches
 * InnerTube captions there, then Render or the React app stores the segments.
 */
header("Content-Type: application/json; charset=utf-8");
header("Cache-Control: no-store");
header("Access-Control-Allow-Origin: *");

if (!function_exists("str_ends_with")) {
    function str_ends_with($haystack, $needle)
    {
        $needle = (string) $needle;
        if ($needle === "") {
            return true;
        }
        return substr((string) $haystack, -strlen($needle)) === $needle;
    }
}

$videoId = isset($_GET["v"]) ? trim($_GET["v"]) : "";
if (!preg_match('/^[A-Za-z0-9_-]{11}$/', $videoId)) {
    http_response_code(400);
    echo json_encode(["error" => "A valid YouTube video ID is required."]);
    exit;
}

$clients = [
    [
        "clientName" => "WEB",
        "clientVersion" => "2.20250925.01.00",
        "hl" => "en",
        "gl" => "US",
        "userAgent" => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "clientNameId" => "1",
    ],
    [
        "clientName" => "ANDROID",
        "clientVersion" => "19.44.38",
        "androidSdkVersion" => 30,
        "osName" => "Android",
        "osVersion" => "14",
        "hl" => "en",
        "gl" => "US",
        "userAgent" => "com.google.android.youtube/19.44.38 (Linux; U; Android 14) gzip",
        "clientNameId" => "3",
    ],
    [
        "clientName" => "WEB_EMBEDDED_PLAYER",
        "clientVersion" => "1.20240920.01.00",
        "clientScreen" => "EMBED",
        "hl" => "en",
        "gl" => "US",
        "userAgent" => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "clientNameId" => "56",
    ],
    [
        "clientName" => "IOS",
        "clientVersion" => "20.10.38",
        "deviceMake" => "Apple",
        "deviceModel" => "iPhone16,2",
        "osName" => "iOS",
        "osVersion" => "18.1.0",
        "hl" => "en",
        "gl" => "US",
        "userAgent" => "com.google.ios.youtube/20.10.38 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)",
        "clientNameId" => "5",
    ],
];

$errors = [];
foreach ($clients as $client) {
    try {
        $segments = fetch_segments($videoId, $client);
        if ($segments) {
            echo json_encode(["segments" => $segments]);
            exit;
        }
    } catch (Throwable $exc) {
        $errors[] = $client["clientName"] . ": " . $exc->getMessage();
    }
}

http_response_code(502);
echo json_encode([
    "error" => "YouTube captions could not be loaded from this host.",
    "detail" => array_slice($errors, 0, 4),
]);

function fetch_segments(string $videoId, array $client): array
{
    $viaNext = fetch_via_next($videoId, $client);
    if ($viaNext) {
        return $viaNext;
    }

    $payload = player_payload($videoId, $client);
    $player = http_json(
        "POST",
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        $payload,
        innertube_headers($client, $videoId)
    );
    $tracks = $player["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"] ?? [];
    if (!is_array($tracks) || !$tracks) {
        $status = $player["playabilityStatus"]["status"] ?? "unknown";
        throw new RuntimeException("No caption tracks (playability={$status}).");
    }
    $track = pick_track($tracks);
    if ($track === null || empty($track["baseUrl"])) {
        throw new RuntimeException("No usable caption track URL.");
    }
    if (!allowed_caption_url($track["baseUrl"])) {
        throw new RuntimeException("Caption URL host was not YouTube.");
    }

    $jsonUrl = with_fmt($track["baseUrl"], "json3");
    $caption = http_text("GET", $jsonUrl, null, innertube_headers($client, $videoId));
    $segments = parse_caption_body($caption);
    if ($segments) {
        return $segments;
    }
    $xmlUrl = with_fmt($track["baseUrl"], "srv3");
    $xml = http_text("GET", $xmlUrl, null, innertube_headers($client, $videoId));
    $segments = parse_caption_body($xml);
    if ($segments) {
        return $segments;
    }
    throw new RuntimeException("Caption file was empty.");
}

function fetch_via_next(string $videoId, array $client): array
{
    if ($client["clientName"] === "WEB_EMBEDDED_PLAYER") {
        return [];
    }
    $payload = player_payload($videoId, $client);
    $next = http_json(
        "POST",
        "https://www.youtube.com/youtubei/v1/next?prettyPrint=false",
        $payload,
        innertube_headers($client, $videoId)
    );
    $params = find_transcript_params($next);
    if (!$params) {
        return [];
    }
    $body = http_json(
        "POST",
        "https://www.youtube.com/youtubei/v1/get_transcript?prettyPrint=false",
        [
            "context" => ["client" => client_body($client)],
            "params" => $params,
        ],
        innertube_headers($client, $videoId)
    );
    return parse_get_transcript($body);
}

function player_payload(string $videoId, array $client): array
{
    $payload = [
        "context" => ["client" => client_body($client)],
        "videoId" => $videoId,
        "contentCheckOk" => true,
        "racyCheckOk" => true,
    ];
    if (in_array($client["clientName"], ["WEB_EMBEDDED_PLAYER", "TVHTML5_SIMPLY_EMBEDDED_PLAYER"], true)) {
        $payload["context"]["thirdParty"] = ["embedUrl" => "https://www.youtube.com/"];
    }
    return $payload;
}

function client_body(array $client): array
{
    $skip = ["userAgent" => true, "clientNameId" => true];
    $body = [];
    foreach ($client as $key => $value) {
        if (!isset($skip[$key])) {
            $body[$key] = $value;
        }
    }
    return $body;
}

function find_transcript_params($node): ?string
{
    if (is_array($node)) {
        if (isset($node["getTranscriptEndpoint"]["params"]) && is_string($node["getTranscriptEndpoint"]["params"])) {
            return $node["getTranscriptEndpoint"]["params"];
        }
        foreach ($node as $value) {
            $found = find_transcript_params($value);
            if ($found) {
                return $found;
            }
        }
    }
    return null;
}

function parse_get_transcript($node): array
{
    $segments = [];
    walk_transcript($node, $segments);
    return $segments;
}

function walk_transcript($node, array &$segments): void
{
    if (!is_array($node)) {
        return;
    }
    if (isset($node["transcriptSegmentRenderer"]) && is_array($node["transcriptSegmentRenderer"])) {
        $renderer = $node["transcriptSegmentRenderer"];
        $startMs = (float) ($renderer["startMs"] ?? 0);
        $endMs = (float) ($renderer["endMs"] ?? $startMs);
        $text = "";
        foreach (($renderer["snippet"]["runs"] ?? []) as $run) {
            $text .= (string) ($run["text"] ?? "");
        }
        $text = trim(preg_replace("/\s+/", " ", str_replace("\n", " ", $text)));
        if ($text !== "") {
            $segments[] = [
                "start" => $startMs / 1000.0,
                "duration" => max(0.0, ($endMs - $startMs) / 1000.0),
                "text" => $text,
            ];
        }
        return;
    }
    foreach ($node as $child) {
        walk_transcript($child, $segments);
    }
}

function pick_track(array $tracks): ?array
{
    $preferred = ["en", "en-US", "en-GB", "en-orig", "a.en"];
    foreach ($preferred as $lang) {
        foreach ($tracks as $track) {
            $code = strtolower((string) ($track["languageCode"] ?? ""));
            if ($code === strtolower($lang) && !empty($track["baseUrl"])) {
                return $track;
            }
        }
    }
    foreach ($tracks as $track) {
        $code = strtolower((string) ($track["languageCode"] ?? ""));
        if (strpos($code, "en") === 0 && !empty($track["baseUrl"])) {
            return $track;
        }
    }
    foreach ($tracks as $track) {
        if (!empty($track["baseUrl"])) {
            return $track;
        }
    }
    return null;
}

function parse_caption_body(string $content): array
{
    $stripped = ltrim($content);
    if ($stripped === "") {
        return [];
    }
    if ($stripped[0] === "{" || $stripped[0] === "[") {
        $payload = json_decode($content, true);
        if (!is_array($payload)) {
            return [];
        }
        return parse_json3($payload);
    }
    return parse_timedtext_xml($content);
}

function parse_json3(array $payload): array
{
    $segments = [];
    foreach ($payload["events"] ?? [] as $event) {
        $text = "";
        foreach ($event["segs"] ?? [] as $seg) {
            $text .= (string) ($seg["utf8"] ?? "");
        }
        $text = trim(preg_replace("/\s+/", " ", str_replace("\n", " ", $text)));
        if ($text === "") {
            continue;
        }
        $segments[] = [
            "start" => ((float) ($event["tStartMs"] ?? 0)) / 1000.0,
            "duration" => ((float) ($event["dDurationMs"] ?? 0)) / 1000.0,
            "text" => $text,
        ];
    }
    return $segments;
}

function parse_timedtext_xml(string $content): array
{
    $xml = @simplexml_load_string($content);
    if ($xml === false) {
        return [];
    }
    $segments = [];
    foreach ($xml->xpath("//text") ?: [] as $node) {
        $text = trim(preg_replace("/\s+/", " ", html_entity_decode((string) $node, ENT_QUOTES | ENT_XML1, "UTF-8")));
        if ($text === "") {
            continue;
        }
        $start = (float) ($node["start"] ?? 0);
        $duration = (float) ($node["dur"] ?? 0);
        $segments[] = ["start" => $start, "duration" => $duration, "text" => $text];
    }
    return $segments;
}

function innertube_headers(array $client, string $videoId): array
{
    return [
        "Content-Type: application/json",
        "User-Agent: " . $client["userAgent"],
        "X-YouTube-Client-Name: " . $client["clientNameId"],
        "X-YouTube-Client-Version: " . $client["clientVersion"],
        "Origin: https://www.youtube.com",
        "Accept-Language: en-US,en;q=0.9",
        "Referer: https://www.youtube.com/embed/{$videoId}",
    ];
}

function with_fmt(string $url, string $fmt): string
{
    $parts = parse_url($url);
    parse_str($parts["query"] ?? "", $query);
    unset($query["fmt"]);
    $query["fmt"] = $fmt;
    $rebuild = ($parts["scheme"] ?? "https") . "://" . ($parts["host"] ?? "www.youtube.com");
    if (!empty($parts["port"])) {
        $rebuild .= ":" . $parts["port"];
    }
    $rebuild .= $parts["path"] ?? "";
    $rebuild .= "?" . http_build_query($query);
    return $rebuild;
}

function allowed_caption_url(string $url): bool
{
    $host = strtolower((string) parse_url($url, PHP_URL_HOST));
    return $host !== "" && (str_ends_with($host, "youtube.com") || str_ends_with($host, "youtube-nocookie.com"));
}

function http_json(string $method, string $url, $payload, array $headers): array
{
    $raw = http_text($method, $url, $payload, $headers);
    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        throw new RuntimeException("YouTube returned a non-JSON body.");
    }
    return $decoded;
}

function http_text(string $method, string $url, $payload, array $headers): string
{
    if (function_exists("curl_init")) {
        $ch = curl_init($url);
        $opts = [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_TIMEOUT => 25,
            CURLOPT_HTTPHEADER => $headers,
        ];
        if (strtoupper($method) === "POST") {
            $opts[CURLOPT_POST] = true;
            $opts[CURLOPT_POSTFIELDS] = json_encode($payload);
        }
        curl_setopt_array($ch, $opts);
        $body = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $err = curl_error($ch);
        curl_close($ch);
        if ($body === false) {
            throw new RuntimeException($err !== "" ? $err : "Caption request failed.");
        }
        if ($code === 403 || $code === 429) {
            throw new RuntimeException("YouTube blocked this host (HTTP {$code}).");
        }
        if ($code >= 400) {
            throw new RuntimeException("YouTube returned HTTP {$code}.");
        }
        return (string) $body;
    }

    $context = stream_context_create([
        "http" => [
            "method" => strtoupper($method),
            "header" => implode("\r\n", $headers),
            "content" => $payload === null ? "" : json_encode($payload),
            "timeout" => 25,
            "ignore_errors" => true,
        ],
    ]);
    $body = @file_get_contents($url, false, $context);
    if ($body === false) {
        throw new RuntimeException("Caption request failed.");
    }
    return $body;
}
