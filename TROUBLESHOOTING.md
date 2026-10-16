# 🛠️ Troubleshooting — 5 common errors and how to fix them

Find your error message below. Each fix is copy-paste simple.

---

## Error 1: `blocked by CORS policy` / `Access-Control-Allow-Origin`

**What it means (simple):** Your website (Vercel) is knocking on the backend's door (Render),
but the backend has a guest list (`CORS_ORIGINS`) and your website isn't on it.

**How to fix:**
1. Go to **Render** → your `opusclip-api` service → **Environment**.
2. Set `CORS_ORIGINS` to BOTH addresses, separated by a comma, **no spaces, no trailing slashes**:
   ```
   http://localhost:3000,https://clipviral.vercel.app
   ```
3. Save → wait for the rebuild (~2 min).
4. Hard-refresh the website (Windows: `Ctrl+Shift+R`, Mac: `Cmd+Shift+R`).

**Most common mistakes:**
- Typo in the Vercel URL (must be `https://...` and exactly match the browser address bar).
- Trailing slash at the end (`https://x.vercel.app/` ❌).
- Changed the Vercel project name → the address changed → update `CORS_ORIGINS` again.

---

## Error 2: `ffmpeg: command not found` / `Command failed: ffmpeg` / `ffprobe: not found`

**What it means:** The video scissors (FFmpeg) isn't installed where the code is running.

**How to fix — pick your situation:**

**A) On Render:** make sure you deployed with **Runtime: Docker** (not "Node" or "Python"),
and **Root Directory: `backend`**. The `backend/Dockerfile` installs FFmpeg automatically.
If you picked the wrong runtime: create a new Web Service with Docker, or in **Settings →
Runtime** switch to Docker and redeploy.

**B) On your own computer (local testing):** install FFmpeg first:
```bash
# Mac
brew install ffmpeg

# Ubuntu / Debian Linux
sudo apt update && sudo apt install -y ffmpeg

# Windows (PowerShell, with winget)
winget install ffmpeg
```
Then check it works:
```bash
ffmpeg -version
```
If Windows says it's still not found: close the terminal, open a NEW one, and try again.

---

## Error 3: `429 Rate limit exceeded` / `rate_limit_exceeded` / `file is larger than 25MB`

**What it means:** The free AI (Groq) is saying "slow down for a minute". Free limits are
plenty for normal use: 20 requests/minute and **8 hours of audio per day**. Also possible:
the per-request 25MB audio limit on very long videos.

**How to fix:**
1. **Wait 60 seconds and retry** — free limits refresh every minute. Re-upload the video;
   nothing is broken.
2. **`file is larger than 25MB`**: already handled! The code automatically chops long audio
   into chunks under 22MB and transcribes them one by one. If you still see this, tell me —
   it means the chunking env needs tuning for a monster file.
3. **Daily limit hit (8 hours of audio/day)**: sleep on it — it resets every day at midnight
   UTC. That's the price of $0, and it's a very high ceiling for a new product.
4. **Using OpenAI instead?** (`AI_PROVIDER=openai`) — that error means billing:
   add a payment method at https://platform.openai.com/settings/organization/billing and
   raise the monthly budget at https://platform.openai.com/settings/organization/limits.
5. **`model_not_found`**: check `AI_PROVIDER` is set and the model matches the provider
   (`openai/gpt-oss-120b` for Groq, `gpt-4o` for OpenAI). The defaults are automatic.

---

## Error 4: `permission denied for table jobs` / empty dashboard / `401 Unauthorized` / `Invalid login token`

**What it means:** Usually one of two things — (a) the database tables were never created, or
(b) the wrong secret key is in the wrong place.

**How to fix:**
1. **Run the schema again**: Supabase → **SQL Editor** → paste ALL of `supabase/schema.sql` →
   **Run**. It is safe to run twice (it says "if not exists" everywhere).
2. **Key placement check** (this confuses everyone):
   - `SUPABASE_SERVICE_ROLE_KEY` → goes ONLY on **Render** (backend). NEVER on Vercel.
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` → goes on **Vercel** (frontend).
   - `SUPABASE_URL` on Render and `NEXT_PUBLIC_SUPABASE_URL` on Vercel must be the SAME project URL.
3. **401 Invalid login token**: your login session expired → log out and log in again.
4. **Still empty?** Make sure you uploaded the video while logged in. The dashboard only shows
   jobs that belong to your account.

---

## Error 5: `502 Bad Gateway` / `504 Gateway Timeout` / job stuck on "Queued" / upload fails on big files

**What it means:** The backend is asleep, restarting, or ran out of free-tier muscle.

**How to fix:**
1. **Sleeping service (most common)**: Render free services nap after ~15 minutes without
   visitors. The first click after waking takes ~60 seconds. Open
   `https://opusclip-api.onrender.com/api/health` first to "wake it up", then retry the website.
2. **See what's really wrong**: Render dashboard → your service → **Logs**. The error text there
   is the truth. Same for Vercel → your project → **Logs**.
3. **Upload too large / times out**: free tier allows up to `MAX_UPLOAD_MB` (default 512) but
   small RAM means big videos can fail. For testing use videos **under ~100 MB**. To raise the
   limit: Render → Environment → add `MAX_UPLOAD_MB=1024` (and use a bigger instance type).
4. **Job stuck at "Queued"**: the background worker died mid-job (service restarted/slept).
   Re-upload the video — jobs cannot resume after a restart on the free plan.
5. **Build failed on Render**: check **Root Directory = `backend`** and **Runtime = Docker**.
   Build logs will name the failing line — usually a typo'd env var or a wrong key.

---

## 💡 Bonus quick fixes

| Symptom | Fix |
|---|---|
| Website shows old version after a code change | Vercel: **Deployments → ⋯ → Redeploy**. Env var changes need a redeploy! |
| `npm: command not found` | Install Node.js from https://nodejs.org (LTS version), open a new terminal. |
| Videos play in dashboard but look cut off | That's the 9:16 vertical crop by design (like OpusClip). |
| Captions in wrong language | Whisper auto-detects. For a specific language, add `language=...` in `transcription.py`. |
| Want a "recap reel" of all clips | Render → Environment → `RECAP_ENABLED=true` (needs more RAM; MoviePy stitches the clips). |

Still stuck? Read the Render/Vercel **Logs** page first — 95% of the time the exact error is
printed there in plain text.
