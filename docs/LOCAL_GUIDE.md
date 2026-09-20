# AdMention AI — Local Run Guide

This is the document to understand **what this project is**, **where it runs**, and **exactly which folder to use for each command**.

Yes: this app is designed to run **on your computer (local)**. You do not need a cloud server.

On this machine it currently runs as:

- **Frontend** at http://localhost:5173 (the website you open in Chrome)
- **Backend** at http://localhost:8000 (the API that talks to YouTube and the database)
- **Database** as a local SQLite file: `backend/admention.db`

Docker / PostgreSQL are optional. They are not required to develop locally.

---

## 1. What this project does

AdMention AI finds advertiser mentions inside a YouTube video transcript.

The intended flow:

```text
Paste YouTube URL
        ↓
Fetch video info (title, channel, thumbnail)
        ↓
Fetch timestamped transcript
        ↓
Search advertiser name (example: Feldman Automotive)
        ↓
Show matches with context + a YouTube link that opens at that second
```

Example result:

- Timestamp: `00:14:32`
- Mention: `Today's show is sponsored by Feldman Automotive`
- Watch link: `https://www.youtube.com/watch?v=VIDEO_ID&t=872s`

---

## 2. Where everything lives

Open this folder in File Explorer or Cursor:

```text
C:\Users\Bharat\Desktop\my-project\AdMention AI
```

That is the **project root**. From here:

| Folder / file | What it is | Do you run commands here? |
| --- | --- | --- |
| `frontend/` | React website | Yes — to start the UI |
| `backend/` | FastAPI API | Yes — to start the server and tests |
| `docs/` | Documentation | No |
| `.env` | Local settings | Edit here, do not run commands |
| `docker-compose.yml` | Optional full stack | Only if Docker Desktop is installed |

You will usually keep **two PowerShell windows** open:

1. Backend window, always inside `backend`
2. Frontend window, always inside `frontend`

---

## 3. First-time setup (do this once)

### Step 3.1 — Create `.env`

**Where:** project root

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI"
copy .env.example .env
```

Then open `.env` and make sure this line is uncommented / set:

```text
DATABASE_URL=sqlite:///./admention.db
```

That file already exists on this computer, so you can skip this if `.env` is present.

### Step 3.2 — Backend Python environment

**Where:** `backend`

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\backend"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

After this, your prompt should show `(.venv)`.

### Step 3.3 — Frontend packages

**Where:** `frontend` (new PowerShell window)

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\frontend"
npm install
```

---

## 4. Start the app locally (every day)

You need **both** processes running.

### Terminal 1 — Backend API

**Where:** `backend`

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\backend"
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

Leave this window open. Success looks like:

```text
Uvicorn running on http://127.0.0.1:8000
```

Check it in the browser:

http://127.0.0.1:8000/api/health

You should see:

```json
{ "status": "ok" }
```

Interactive API docs:

http://127.0.0.1:8000/docs

### Terminal 2 — Frontend website

**Where:** `frontend`

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\frontend"
npm run dev
```

Leave this window open. Then open:

http://localhost:5173

The website talks to the backend at port `8000`. If the backend is not running, the page will show **Backend unavailable**.

---

## 5. How to use it (local walkthrough)

1. Keep both terminals running.
2. Open http://localhost:5173
3. Confirm the badge says **Backend ok**
4. Paste a public YouTube URL, for example:

```text
https://www.youtube.com/watch?v=xAEEHloK5OQ
```

5. Click **Analyze Video**
6. You should see title, channel, thumbnail, and transcript status
7. Type an advertiser or phrase in **Find mentions**
8. Click **Find Mentions**
9. Click **Watch on YouTube** to open that exact timestamp

Notes:

- Analyze can take 10–30 seconds because it fetches captions from YouTube.
- Duration and published date stay empty unless you add `YOUTUBE_API_KEY` in `.env`.
- Title, channel, and thumbnail still work without that key.

---

## 6. Where to run tests

### Backend tests

**Where:** `backend`

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\backend"
.\.venv\Scripts\activate
python -m pytest tests -q
```

These tests use an in-memory database. They do not need the website running.

### Frontend tests

**Where:** `frontend`

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI\frontend"
npm test
```

---

## 7. Optional: call the API yourself

Backend must be running first.

**Where:** any PowerShell window

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Analyze a video:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/videos/analyze `
  -ContentType "application/json" `
  -Body '{"youtube_url":"https://www.youtube.com/watch?v=xAEEHloK5OQ"}'
```

Get transcript:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/videos/xAEEHloK5OQ/transcript
```

Create advertiser:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/advertisers `
  -ContentType "application/json" `
  -Body '{"name":"Feldman Automotive","aliases":["Feldman","Feldman Auto"]}'
```

Search mentions:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/mentions/search `
  -ContentType "application/json" `
  -Body '{"video_id":"xAEEHloK5OQ","advertiser":"Feldman Automotive"}'
```

Or use the visual tester: http://127.0.0.1:8000/docs

---

## 8. Whole project map (all 15 phases)

This is the full product plan. Phases 1–8 are implemented. Phase 9 (dashboard polish / browser verification) is current. Later phases are not finished.

```text
YouTube URL
    ↓  Phase 2  video metadata
    ↓  Phase 3  timestamped transcript
    ↓  Phase 4  Whisper only if captions are missing
    ↓  Phase 5  advertiser names + aliases
    ↓  Phase 6  find mentions in transcript
    ↓  Phase 7  surrounding context
    ↓  Phase 8  YouTube timestamp link
    ↓  Phase 9  website dashboard
    ↓  Phase 10 filters + pagination
    ↓  Phase 11 AI verification of mention type
    ↓  Phase 12 smarter matching
    ↓  Phase 13 CSV reports
    ↓  Phase 14 video clips
    ↓  Phase 15 auto-ingest a whole channel
```

| Phase | What it is | Run / see it here | Status |
| --- | --- | --- | --- |
| 1 Foundation | App skeleton, health check, database | Backend + frontend start | Done |
| 2 YouTube processing | Accept URL, save title/channel/thumbnail | Analyze Video on the website, or `POST /api/videos/analyze` | Done |
| 3 Transcript | Store caption lines with timestamps | After analyze, `GET /api/videos/{id}/transcript` | Done |
| 4 Whisper | Backup if YouTube has no captions | Optional; off by default | Done (local Whisper not installed) |
| 5 Advertisers | Create Feldman Automotive + aliases | `POST /api/advertisers` | Done |
| 6 Mentions | Search transcript for advertiser | Find Mentions on the website | Done |
| 7 Context | 2 lines before / 2 after | Included in search results | Done |
| 8 Timestamp links | `watch?v=...&t=872s` | Watch on YouTube button | Done |
| 9 Dashboard | The React UI at `:5173` | Browser | In progress |
| 10 Filtering | Filter by advertiser, date, type | Not built yet | Pending |
| 11 AI verification | OpenAI classifies mention type | Needs `OPENAI_API_KEY` later | Pending |
| 12 Smart matching | Better matching, fewer false hits | Not built yet | Pending |
| 13 Reporting | CSV export | Not built yet | Pending |
| 14 Clips | Cut a short MP4 around a mention | Needs FFmpeg later | Pending |
| 15 Ingestion | Watch a channel for new videos | Not built yet | Pending |

---

## 9. How local mode actually works

```text
Your Chrome
   http://localhost:5173
            │
            │  React app in frontend/
            ▼
   FastAPI in backend/   http://localhost:8000
            │
            ├── SQLite file: backend/admention.db
            ├── YouTube oEmbed (title, channel, thumbnail)
            └── YouTube captions (usually via yt-dlp)
```

Important:

- This is **local**, not deployed to the internet.
- Only you can open it, using `localhost` on this PC.
- The database file is created automatically in `backend/admention.db`.
- Restarting the servers does not delete that file.
- Closing the two terminal windows stops the app.

---

## 10. Optional later setup

### YouTube duration + published date

Edit `.env` in the **project root**:

```text
YOUTUBE_API_KEY=your_key_here
```

Keep it server-side. Never put it in the React app.

Restart the backend terminal after changing `.env`.

### Docker (only if you install Docker Desktop)

**Where:** project root

```powershell
cd "C:\Users\Bharat\Desktop\my-project\AdMention AI"
docker compose up --build
```

Then PostgreSQL is used instead of SQLite.

---

## 11. If something fails

| Symptom | What to do |
| --- | --- |
| `Backend unavailable` on the website | Start Terminal 1 (backend) first |
| Port 8000 already in use | Close the old backend window, or use `--port 8001` and update `.env` `VITE_API_BASE_URL` |
| `No module named app` | You are in the wrong folder. `cd backend` first |
| `npm` not found | Install Node.js, then run `npm install` in `frontend` |
| Analyze is slow | Normal. Caption download can take a while |
| Duration is empty | Expected without `YOUTUBE_API_KEY` |
| Docker commands fail | Expected on this PC until Docker Desktop is installed. Use the local SQLite steps above |

---

## 12. Related docs

| File | Read it for |
| --- | --- |
| `README.md` | Short project overview |
| `docs/LOCAL_GUIDE.md` | This file — how to run locally |
| `docs/api.md` | Every API request/response |
| `docs/development.md` | What each completed phase verified |
| `CURSOR_PROJECT.md` | Full original product spec |
