# Development Notes

## Phase 1 — Project Foundation (complete)

Implemented:

- FastAPI backend with `GET /api/health`
- React + Vite + Tailwind frontend
- SQLAlchemy models and Alembic initial migration
- Docker Compose for frontend, backend, and PostgreSQL
- Automated backend and frontend tests

Verified:

- Backend starts at `http://127.0.0.1:8000`
- Frontend starts at `http://localhost:5173`
- Health endpoint returns `{"status":"ok"}` and executes `SELECT 1`
- Frontend health badge shows `Backend ok`

### Blocker

Docker Desktop and PostgreSQL are not installed on this development machine. Local development uses SQLite via `DATABASE_URL=sqlite:///./admention.db`. Docker Compose is ready for when Docker is available. Tests use in-memory SQLite.

When Docker Desktop is installed:

```bash
copy .env.example .env
docker compose up --build
```

The production-intended database remains PostgreSQL.

## Phase 2 — YouTube Processing (complete)

Implemented:

- URL parser supporting `/watch`, `youtu.be`, `/live`, timestamp query params, and extra query params
- `YouTubeService`: `validate_url()`, `extract_video_id()`, `get_video_metadata()`, `normalize_video_url()`, `generate_timestamp_url()`
- `YouTubeProvider` (alias `YouTubeMetadataProvider`) using live oEmbed plus optional Data API enrichment
- `videos` model with unique `youtube_video_id` (Alembic revision `0001_initial`)
- `POST /api/videos/analyze` upserts metadata and returns `transcript_status: pending`
- User-friendly errors for invalid URLs, missing/private videos, quota, timeout, malformed responses, and database failures

Verified:

- Backend unit and API tests pass with mocked YouTube responses (`pytest`, 52 passed)
- Ruff lint passed on `app` and `tests`
- Live oEmbed analyze of Woodward Sports video `https://www.youtube.com/watch?v=xAEEHloK5OQ` returned:

```text
video_id: xAEEHloK5OQ
title: Detroit Lions Star Returns!? | Woodward Heavyweights | July 22nd 2026
channel: WoodwardSports
thumbnail_url: https://i.ytimg.com/vi/xAEEHloK5OQ/hqdefault.jpg
transcript_status: pending
```

- Invalid URL `https://google.com` returns `400`
- Unknown video ID returns `404` (`This video was not found or has been deleted.`)

### Limitations

- `YOUTUBE_API_KEY` is not set. `published_at` and `duration_seconds` remain `null` because oEmbed does not provide them. Data API enrichment is implemented and covered by mocks.
- Docker Desktop is not installed, so Compose/PostgreSQL was not re-verified. Local development still uses SQLite. `docker-compose.yml` is unchanged from Phase 1.

## Phase 3 — Transcript Engine (complete)

Implemented:

- `TranscriptProvider` interface
- `YouTubeTranscriptProvider` (`youtube-transcript-api`)
- `YtDlpTranscriptProvider` as a YouTube caption fallback when the official transcript API returns empty XML
- `TranscriptService` to retrieve, normalize, store, skip duplicates, and read timestamped segments
- `transcript_segments` table (Alembic revision `0001_initial`)
- `POST /api/videos/analyze` now ingests a transcript after metadata
- `GET /api/videos/{video_id}/transcript`

Verified:

- Unit tests cover normalization, exact timestamp persistence (`872.4`), empty/unavailable transcripts, duplicate-skip, and the GET endpoint
- Backend tests: 59 passed; ruff passed
- Live Woodward Sports video `https://www.youtube.com/watch?v=xAEEHloK5OQ`:
  - `youtube-transcript-api` failed with empty XML (`ParseError`) and was treated as unavailable
  - yt-dlp retrieved **3902** real caption segments
  - First cue: `start=1.28`, `duration=4.614`, text begins `I [music] just smoked another to the`
  - `GET /api/videos/xAEEHloK5OQ/transcript` returned `transcript_status=available`

Whisper is implemented as a provider class but is **not** in the default chain until Phase 4.

## Phase 4 — Whisper Fallback (complete)

Implemented:

- `WhisperTranscriptProvider` on the same `TranscriptProvider` interface
- Default chain: YouTube captions → yt-dlp captions → local caption fixture → Whisper
- `WHISPER_ENABLED=false` by default so missing captions do not invent audio transcripts
- `WHISPER_PROVIDER=mock` loads `backend/fixtures/whisper/sample.json`
- `WHISPER_PROVIDER=local` transcribes a local audio file with `openai-whisper` when installed
- No paid transcription service

Verified:

- Short local sample cues: `start=0.0` / `2.4` with exact fixture text
- Local WAV transcription path preserves Whisper segment start/end as transcript timestamps
- Disabled Whisper returns unavailable and does not break analyze
- Backend tests: 64 passed; ruff passed

Local Whisper is **not** installed in this environment (no `openai-whisper` / ffmpeg). Real model transcription is pending that install. The provider, mock sample, and transcribe-file path are tested.

## Phase 5 — Advertiser Management (complete)

Implemented:

- `advertisers` and `advertiser_aliases` tables
- Alembic migration `0002_advertiser_alias_unique`
- CRUD: `POST/GET/PUT/DELETE /api/advertisers` and alias create/delete
- Case-insensitive duplicate prevention for names and aliases
- Feldman Automotive with aliases Feldman and Feldman Auto

Verified:

- Create with aliases returns 201
- Duplicate `feldman automotive` returns 409
- Duplicate alias `feldman` returns 409
- Alias equal to the advertiser name is rejected
- GET missing advertiser returns 404
- Backend tests: 68 passed; ruff passed

## Phase 6 — Mention Detection (complete)

Implemented:

- `MentionSearchService` with normalized, word-boundary, case-insensitive matching
- Exact advertiser name and alias matching
- `mentions` rows stored with `mention_type=unknown` and deterministic confidence (`1.0` exact, `0.9` alias)
- `POST /api/mentions/search`
- No AI

Verified by automated tests: exact Feldman Automotive hits, alias Feldman Auto, empty results, missing video 404, partial-word rejection (`Feldmanesque`), and persisted mention rows.

## Phase 7 — Mention Context (complete)

Default context is 2 segments before and 2 after the match. Override with `context_before` and `context_after` on the search request (also `MENTION_CONTEXT_BEFORE` / `MENTION_CONTEXT_AFTER`).

## Phase 8 — Timestamp Links (complete)

Transcript `start_seconds` are formatted with `format_timestamp()` and linked with:

`https://www.youtube.com/watch?v=VIDEO_ID&t=872s`

via `generate_youtube_timestamp_url()`. 872.4 seconds becomes `t=872s` and display `00:14:32`.

## Phase 9 — React Dashboard (in progress)

The existing dashboard flow is:

YouTube URL → Analyze Video → Video information → Find mentions → Results.

Results columns: Timestamp, Mention, Context, Type, Confidence, Watch.

Live browser verification of the updated Confidence column and `watch?v=&t=872s` links is the remaining Phase 9 gate.

## Blockers and local fallbacks

1. **Docker / PostgreSQL** — not installed. SQLite is the local database. `docker-compose.yml` is ready.
2. **YouTube Data API key** — not set. `published_at` and `duration_seconds` stay null. Title/channel/thumbnail were verified live via oEmbed.
3. **youtube-transcript-api** — empty XML (`ParseError`) from this machine. yt-dlp caption fallback works (verified on Woodward Sports).
4. **Whisper** — optional and not installed. Mock local sample is tested. Enable with ffmpeg + `openai-whisper`.

## Health check

`GET /api/health` executes `SELECT 1` against the configured database and returns:

```json
{
  "status": "ok"
}
```
