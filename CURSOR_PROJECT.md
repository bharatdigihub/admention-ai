# AdMention AI — Sequential Development Execution

You are the primary senior full-stack engineer responsible for implementing this project.

The project specification is in:

`CURSOR_PROJECT.md`

Phase 1 has already been completed and verified.

Your job now is to implement the remaining project phases **sequentially and completely**.

---

# CRITICAL EXECUTION RULE

You MUST work on exactly ONE phase at a time.

The workflow for every phase is:

```text
READ PHASE REQUIREMENTS
        ↓
INSPECT EXISTING CODE
        ↓
CREATE IMPLEMENTATION PLAN
        ↓
IMPLEMENT
        ↓
RUN TESTS
        ↓
RUN LINT / TYPE CHECK
        ↓
FIX ERRORS
        ↓
MANUAL VERIFICATION
        ↓
UPDATE DOCUMENTATION
        ↓
MARK PHASE COMPLETE
        ↓
MOVE TO NEXT PHASE
```

Do NOT skip testing.

Do NOT mark a phase complete just because the code was generated.

Do NOT move to the next phase if the current phase has unresolved errors.

Do NOT rewrite working code unnecessarily.

Do NOT ask me to manually create files or write code unless absolutely necessary.

You have permission to create and modify project files.

---

# PHASE STATUS

Current status:

```text
Phase 1 — Project Foundation       ✅ COMPLETE
Phase 2 — YouTube Processing       ✅ COMPLETE
Phase 3 — Transcript Engine        ✅ COMPLETE
Phase 4 — Whisper Fallback         ✅ COMPLETE
Phase 5 — Advertiser Management    ✅ COMPLETE
Phase 6 — Mention Detection        ✅ COMPLETE
Phase 7 — Mention Context          ✅ COMPLETE
Phase 8 — Timestamp Links          ✅ COMPLETE
Phase 9 — Main Dashboard           ⏳ CURRENT
Phase 6 — Mention Detection        ⏳
Phase 7 — Mention Context          ⏳
Phase 8 — Timestamp Links          ⏳
Phase 9 — Main Dashboard           ⏳
Phase 10 — Filtering               ⏳
Phase 11 — AI Verification         ⏳
Phase 12 — Smart Matching          ⏳
Phase 13 — Reporting               ⏳
Phase 14 — Video Clips             ⏳
Phase 15 — Automated Ingestion     ⏳
```

Phase 8 is complete. Continue with **Phase 9**.

---

# PHASE 2 — YouTube Processing

## Objective

Allow the application to accept a YouTube URL and retrieve reliable video metadata.

The user should be able to provide:

```text
https://www.youtube.com/watch?v=VIDEO_ID
```

and the backend should return:

* Video ID
* Title
* Channel
* Published date
* Duration
* Thumbnail
* Original URL
* Transcript status

---

## Step 2.1 — Inspect Existing Project

Before coding:

1. Inspect the complete existing project structure.
2. Read `CURSOR_PROJECT.md`.
3. Review Phase 1 implementation.
4. Identify existing:

   * FastAPI configuration
   * Database configuration
   * SQLAlchemy setup
   * Pydantic schemas
   * API router structure
   * Docker configuration
   * Testing setup
5. Reuse existing architecture where appropriate.

Do not duplicate existing functionality.

---

# Step 2.2 — YouTube URL Parser

Create a reusable YouTube URL parser.

It must support:

```text
https://www.youtube.com/watch?v=VIDEO_ID

https://youtu.be/VIDEO_ID

https://www.youtube.com/live/VIDEO_ID

https://www.youtube.com/watch?v=VIDEO_ID&t=120

https://www.youtube.com/watch?v=VIDEO_ID&feature=share
```

It must extract only:

```text
VIDEO_ID
```

It must reject:

```text
https://google.com

https://example.com/video

invalid strings

empty strings
```

Write unit tests for every supported format.

---

# Step 2.3 — YouTube Service

Create a service abstraction:

```text
YouTubeService
```

Responsibilities:

```text
validate_url()
extract_video_id()
get_video_metadata()
normalize_video_url()
generate_timestamp_url()
```

Do not put this logic directly inside FastAPI routes.

---

# Step 2.4 — YouTube Provider

Create a provider abstraction so YouTube API implementation is isolated.

Example:

```text
YouTubeProvider
```

If the official YouTube Data API is used:

* Keep the API key server-side.
* Read it from environment variables.
* Never expose it to React.
* Never commit it to Git.
* Handle quota/API failures.
* Handle unavailable videos.

Do not fake metadata.

If an API key is not available in the environment:

* Implement the provider correctly.
* Create mock-based tests.
* Document the required configuration.
* Do not pretend that real metadata retrieval has been verified.

---

# Step 2.5 — Database

Create/update the `videos` table.

Required fields:

```text
id
youtube_video_id
url
title
channel_name
published_at
duration_seconds
thumbnail_url
transcript_status
created_at
updated_at
```

Add a unique constraint on:

```text
youtube_video_id
```

Create an Alembic migration.

Do not manually modify the database schema.

---

# Step 2.6 — API Endpoint

Create:

```text
POST /api/videos/analyze
```

Request:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Response:

```json
{
  "video_id": "VIDEO_ID",
  "title": "Example Video",
  "channel": "Woodward Sports",
  "published_at": "2026-09-20T10:00:00Z",
  "duration_seconds": 7200,
  "thumbnail_url": "...",
  "transcript_status": "pending"
}
```

The endpoint must:

1. Validate URL.
2. Extract video ID.
3. Retrieve metadata.
4. Store/update the video.
5. Return the stored video information.

Use appropriate HTTP status codes.

---

# Step 2.7 — Error Handling

Handle:

```text
Invalid URL
Missing video ID
Video does not exist
Video deleted
Video private
YouTube API failure
YouTube API quota error
Timeout
Database failure
Malformed API response
```

Return user-friendly API errors.

Do not expose stack traces.

Log technical details server-side.

---

# Step 2.8 — Testing

Create tests for:

### URL parser

Test:

```text
youtube.com/watch
youtu.be
youtube.com/live
watch URL with timestamp
watch URL with extra query parameters
invalid domain
empty input
malformed URL
```

### YouTube service

Test:

```text
valid video
invalid video
provider error
timeout
```

### API

Test:

```text
successful request
invalid request
provider failure
database failure
```

Use mocked provider responses for tests.

Do not make automated tests dependent on the real YouTube API.

---

# Step 2.9 — Real Manual Test

If `YOUTUBE_API_KEY` is configured:

Use a real public YouTube video.

Test with a Woodward Sports video.

Verify:

```text
Video ID
Title
Channel
Published date
Duration
Thumbnail
```

Make sure the returned data is real.

Do not fabricate successful results.

If the API key is unavailable, clearly report:

```text
Automated tests passed using mocks.
Real YouTube metadata test is pending API credentials.
```

---

# Step 2.10 — Documentation

Update:

```text
README.md
docs/api.md
docs/development.md
```

Document:

* YouTube API setup
* Environment variables
* Endpoint
* Request example
* Response example
* Error responses
* Local testing

---

# PHASE 2 COMPLETION CHECKLIST

Do not mark Phase 2 complete until:

[ ] YouTube URL parser works

[ ] All supported URL formats tested

[ ] Invalid URLs rejected

[ ] YouTube provider implemented

[ ] Database model created

[ ] Alembic migration created

[ ] `/api/videos/analyze` implemented

[ ] API tests pass

[ ] Unit tests pass

[ ] Lint passes

[ ] Type checking passes where applicable

[ ] Docker environment works

[ ] Documentation updated

[ ] Real YouTube test completed OR API credential limitation documented

---

# PHASE 3 — Transcript Engine

Only begin this phase after Phase 2 is completely verified.

Objective:

```text
YouTube Video
      ↓
Timestamped Transcript
      ↓
PostgreSQL
```

Create:

```text
TranscriptProvider
YouTubeTranscriptProvider
TranscriptService
```

Transcript segment:

```json
{
  "start": 872.4,
  "duration": 4.2,
  "text": "Today's show is sponsored by Feldman Automotive"
}
```

Create:

```text
transcript_segments
```

Fields:

```text
id
video_id
start_seconds
duration
text
created_at
```

Requirements:

* Retrieve timestamped transcript.
* Normalize transcript.
* Store segments.
* Avoid duplicate processing.
* Handle unavailable transcripts.
* Handle videos with no transcript.
* Preserve timestamps accurately.
* Add tests.
* Add API endpoint to retrieve transcript.
* Update documentation.

Do NOT implement advertiser detection yet.

---

# PHASE 4 — Whisper Fallback

Only begin after Phase 3 passes.

Create:

```text
WhisperTranscriptProvider
```

Architecture:

```text
YouTube Transcript
       ↓
Available?
   ↓ YES
Use it

   ↓ NO

Whisper
   ↓
Timestamped transcript
```

Keep Whisper behind the same provider interface.

Prefer local Whisper for development.

Do not require a paid transcription service unless necessary.

Test with a short local sample.

Document installation requirements.

---

# PHASE 5 — Advertiser Management

Create:

```text
advertisers
advertiser_aliases
```

Implement:

```text
POST /api/advertisers
GET /api/advertisers
GET /api/advertisers/{id}
PUT /api/advertisers/{id}
DELETE /api/advertisers/{id}
```

Alias management:

```text
POST /api/advertisers/{id}/aliases
DELETE /api/advertisers/{id}/aliases/{alias_id}
```

Support:

```text
Feldman Automotive
Feldman
Feldman Auto
```

Prevent duplicates.

Add tests.

---

# PHASE 6 — Mention Detection

Create:

```text
MentionSearchService
```

Initial algorithm:

```text
Transcript
   ↓
Normalize text
   ↓
Exact advertiser match
   ↓
Alias match
   ↓
Return matching segments
```

Create:

```text
mentions
```

Fields:

```text
id
video_id
advertiser_id
transcript_segment_id
timestamp_seconds
matched_text
mention_type
confidence
created_at
```

Initial values:

```text
mention_type = unknown
confidence = deterministic score
```

Do not use AI yet.

Prioritize accuracy.

---

# PHASE 7 — Mention Context

For every match return:

```text
Previous segments
+
Matched segment
+
Following segments
```

Default:

```text
2 before
1 matching
2 after
```

Make context size configurable.

---

# PHASE 8 — Timestamp Links

Generate:

```text
https://www.youtube.com/watch?v=VIDEO_ID&t=872s
```

Timestamp must originate from transcript data.

Create:

```text
format_timestamp()
generate_youtube_timestamp_url()
```

Test thoroughly.

---

# PHASE 9 — React Dashboard

Build:

```text
AdMention AI
```

Dashboard flow:

```text
YouTube URL
     ↓
Analyze Video
     ↓
Video Information
     ↓
Advertiser
     ↓
Find Mentions
     ↓
Results
```

Results:

```text
Timestamp
Mention
Context
Type
Confidence
Watch
```

Make it responsive and professional.

---

# PHASE 10 — Filtering

Add:

* Advertiser
* Video/show
* Date range
* Mention type
* Confidence

Use backend pagination.

Do not load large datasets into the browser.

---

# PHASE 11 — AI Verification

Only now introduce OpenAI.

Create:

```text
AIProvider
OpenAIProvider
```

Send only small relevant transcript contexts.

Return:

```json
{
  "is_mention": true,
  "mention_type": "ad_read",
  "confidence": 0.98
}
```

Allowed types:

```text
ad_read
sponsored_segment
host_read
organic
unknown
```

Never allow AI to generate timestamps.

Timestamps must come from transcript data.

---

# PHASE 12 — Smart Matching

Add:

```text
Exact matching
Alias matching
Normalized matching
Optional semantic matching
AI verification
```

Optimize for low false positives.

---

# PHASE 13 — Reporting

Add CSV export.

Filters:

```text
Advertiser
Video
Date range
Mention type
```

CSV:

```text
Advertiser
Video
Channel
Date
Timestamp
Mention Type
Confidence
Matched Text
YouTube URL
```

---

# PHASE 14 — Video Clips

Use FFmpeg.

Architecture:

```text
Mention
   ↓
Timestamp
   ↓
Start/end padding
   ↓
FFmpeg
   ↓
MP4
```

Support:

* clip creation
* processing status
* preview
* storage
* download

Do not process videos unnecessarily.

Respect applicable YouTube terms, permissions, and copyright requirements.

---

# PHASE 15 — Automated Ingestion

Eventually:

```text
YouTube Channel
       ↓
New Videos
       ↓
Processing Queue
       ↓
Transcript
       ↓
Advertiser Detection
       ↓
AI Verification
       ↓
Reports
```

Only introduce background workers/queues when necessary.

---

# FINAL MVP VALIDATION

After all required MVP phases are complete, run the complete workflow using a real public YouTube video:

```text
YouTube URL
      ↓
Video metadata
      ↓
Transcript
      ↓
Advertiser
      ↓
Mention detection
      ↓
Context
      ↓
Timestamp
      ↓
YouTube timestamp link
```

Test with:

```text
Feldman Automotive
```

if the test video actually contains that advertiser.

Do not claim a mention exists unless it is actually present in the transcript.

---

# FINAL REPORT

When development is complete, provide:

## Architecture

Explain the complete architecture.

## Technologies

List all technologies used.

## Database

Provide the final schema.

## APIs

List all API endpoints.

## AI

Explain exactly where AI is used and why.

## External Services

List all third-party services and whether they are:

* Free
* Paid
* Optional

## Environment Variables

List required variables.

## Installation

Provide exact commands.

## Testing

Explain how to run all tests.

## Known Limitations

Be honest about:

* YouTube transcript availability
* Whisper processing
* API quotas
* timestamp accuracy
* AI classification limitations
* video clipping limitations

## Future Improvements

List logical next steps.

---

# MOST IMPORTANT RULE

Build this like a real production application.

Do not optimize for "lots of code".

Optimize for:

1. Correctness
2. Timestamp accuracy
3. Reliability
4. Maintainability
5. Testability
6. Low API cost
7. Good user experience

Never fabricate data.

Never hide errors.

Never skip tests.

Never use AI when deterministic code is sufficient.

Always preserve the original transcript timestamps.

Proceed sequentially from Phase 2 onward.
