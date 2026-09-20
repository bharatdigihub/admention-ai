# Deploy: Render API + Hostinger frontend

Live split:

| Piece | Where | URL |
| --- | --- | --- |
| Python / FastAPI | [Render](https://render.com) web service | `https://admention-ai.onrender.com` (confirm after first deploy) |
| React dashboard | Hostinger FTP (`/adverify`) | [https://adverify.codewithbharat.dev](https://adverify.codewithbharat.dev/) |

The React app calls the Render API. CORS on the backend allows `https://adverify.codewithbharat.dev`.

Repo: [github.com/bharatdigihub/admention-ai](https://github.com/bharatdigihub/admention-ai)

```text
Browser  →  https://adverify.codewithbharat.dev   (static React on Hostinger)
                 │
                 │  fetch /api/...
                 ▼
            Render Python  (FastAPI + SQLite)
```

---

## 1. Create the Render Python service

1. Sign in at [dashboard.render.com](https://dashboard.render.com).
2. **New** → **Blueprint** and select `bharatdigihub/admention-ai`, **or** **New** → **Web Service** and connect that repo.
3. If you create the service manually (not Blueprint):

   | Setting | Value |
   | --- | --- |
   | Runtime | Python 3 |
   | Root Directory | `backend` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Health Check Path | `/api/health` |

4. Environment variables:

   | Key | Value |
   | --- | --- |
   | `APP_ENV` | `production` |
   | `DATABASE_URL` | `sqlite:///./admention.db` |
   | `BACKEND_CORS_ORIGINS` | `https://adverify.codewithbharat.dev` |
   | `YOUTUBE_API_KEY` | optional |

5. Deploy, then open `https://YOUR-SERVICE.onrender.com/api/health`. You should see `{"status":"ok"}`.

Free Render services sleep when idle. The first request after sleep can take about a minute. SQLite on the free plan is wiped on each new deploy unless you attach a disk.

If YouTube captions fail from Render, that is usually a datacenter IP block, not a frontend bug.

---

## 2. Point the React app at Render

`frontend/public/config.js` is copied into the Hostinger upload. After Render gives you a URL, set:

```js
window.__API_BASE__ = "https://YOUR-SERVICE.onrender.com";
```

No trailing slash. If the service name stays `admention-ai`, the default file already matches.

---

## 3. Build and upload the frontend to adverify

From the project `frontend` folder:

```bash
npm install
npm run build
```

Upload **everything inside** `frontend/dist/` to Hostinger FTP folder `/adverify` (the document root for `adverify.codewithbharat.dev`). Include:

- `index.html`
- `config.js` (with the real Render URL)
- `.htaccess` (SPA routing)
- `assets/`

Keep Hostinger DNS on the shared host. Do **not** CNAME `adverify` to Render; only the API lives on Render.

---

## 4. Check the live app

1. `https://YOUR-SERVICE.onrender.com/api/health` → `{"status":"ok"}`
2. [https://adverify.codewithbharat.dev](https://adverify.codewithbharat.dev/) → dashboard
3. Analyze a YouTube URL and search an advertiser

If the UI says the backend is unavailable, wait for Render to wake, then confirm `config.js` matches the Render URL.

---

## What will not work

| Host | Role |
| --- | --- |
| Hostinger shared FTP | Static React only. Cannot run FastAPI. |
| Render Python web service | API + database. |
| Pointing `adverify` CNAME at Render | Not used in this split. The subdomain stays on Hostinger. |

---

## Optional: one Docker container (VPS)

`Dockerfile` and `docker-compose.prod.yml` still package UI + API together if you later use a VPS. That is not required for the Render + adverify setup.
