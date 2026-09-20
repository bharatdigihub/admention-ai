# API

Base URL for local development: `http://localhost:8000`

All error responses use:

```json
{ "detail": "User-friendly message" }
```

Stack traces are never returned to the client. Technical details are written to server logs.

---

## `GET /api/health`

Verifies that the API process is running and can query the database.

### Response `200`

```json
{ "status": "ok" }
```

---

## `POST /api/videos/analyze`

Accepts a YouTube URL, extracts the video ID, retrieves public metadata, upserts the `videos` row, and returns the stored record.

Transcript ingestion is not part of this endpoint. `transcript_status` is stored as `pending`.

### Request

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Supported URL formats:

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/live/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID&t=120`
- `https://www.youtube.com/watch?v=VIDEO_ID&feature=share`

### Response `200`

```json
{
  "video_id": "xAEEHloK5OQ",
  "title": "Detroit Lions Star Returns!? | Woodward Heavyweights | July 22nd 2026",
  "channel": "WoodwardSports",
  "published_at": "2026-07-22T21:00:00Z",
  "duration_seconds": 7245,
  "thumbnail_url": "https://i.ytimg.com/vi/xAEEHloK5OQ/hqdefault.jpg",
  "transcript_status": "pending"
}
```

`published_at` and `duration_seconds` are populated only when `YOUTUBE_API_KEY` is configured. Without a Data API key, those fields are `null` and title, channel, and thumbnail still come from live YouTube oEmbed data.

Analyze also attempts to ingest a timestamped transcript. `transcript_status` is one of `pending`, `available`, `fixture`, or `unavailable`.

### Error responses

| Status | When |
| --- | --- |
| `400` | Invalid, empty, or non-YouTube URL |
| `404` | Video does not exist, was deleted, or is private/unavailable |
| `422` | Request body failed schema validation |
| `429` | YouTube Data API quota exceeded (mocked in tests; live oEmbed still succeeds when enrichment is skipped) |
| `500` | Database write failed |
| `502` | YouTube request failed or returned a malformed payload |
| `504` | YouTube request timed out |

Examples:

```json
{ "detail": "The URL is not a valid YouTube video URL." }
```

```json
{ "detail": "This video was not found or has been deleted." }
```

```json
{ "detail": "YouTube took too long to respond. Please try again." }
```

---

## `GET /api/videos/{video_id}/transcript`

Returns stored timestamped transcript segments for a previously analyzed YouTube video ID.

`video_id` is the 11-character YouTube ID, not the internal database primary key.

### Response `200`

```json
{
  "video_id": "xAEEHloK5OQ",
  "transcript_status": "available",
  "segments": [
    {
      "start": 872.4,
      "duration": 4.2,
      "text": "Today's show is sponsored by Feldman Automotive"
    }
  ]
}
```

If captions could not be retrieved, the response is still `200` with `"transcript_status": "unavailable"` and `"segments": []`.

### Error responses

| Status | When |
| --- | --- |
| `404` | The video has not been analyzed yet |

```json
{ "detail": "Video was not found. Analyze the YouTube URL first." }
```

---

## Advertisers

### `POST /api/advertisers`

```json
{
  "name": "Feldman Automotive",
  "aliases": ["Feldman", "Feldman Auto"]
}
```

Response `201`:

```json
{
  "id": 1,
  "name": "Feldman Automotive",
  "aliases": [
    { "id": 1, "alias": "Feldman" },
    { "id": 2, "alias": "Feldman Auto" }
  ]
}
```

Duplicate names return `409`.

### `GET /api/advertisers`

Returns all advertisers, ordered by name.

### `GET /api/advertisers/{id}`

Returns one advertiser or `404`.

### `PUT /api/advertisers/{id}`

```json
{ "name": "Feldman Automotive Group" }
```

### `DELETE /api/advertisers/{id}`

Returns `204`. Aliases are deleted with the advertiser.

### `POST /api/advertisers/{id}/aliases`

```json
{ "alias": "Feldman Auto" }
```

### `DELETE /api/advertisers/{id}/aliases/{alias_id}`

Removes one alias and returns the updated advertiser.

---

## `POST /api/mentions/search`

Deterministic mention search. No AI. Timestamps come from stored transcript segments.

```json
{
  "video_id": "VIDEO_ID",
  "advertiser": "Feldman Automotive",
  "context_before": 2,
  "context_after": 2
}
```

`context_before` and `context_after` default to 2.

Response `200`:

```json
{
  "advertiser": "Feldman Automotive",
  "total_mentions": 1,
  "mentions": [
    {
      "timestamp_seconds": 872.4,
      "timestamp": "00:14:32",
      "text": "Today's show is sponsored by Feldman Automotive",
      "matched_text": "Feldman Automotive",
      "context_before": "Previous segment text",
      "context_after": "Following segment text",
      "mention_type": "unknown",
      "confidence": 1.0,
      "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID&t=872s"
    }
  ]
}
```

Exact name matches use confidence `1.0`. Alias-only matches use `0.9`. `mention_type` is `unknown` until AI verification (Phase 11).