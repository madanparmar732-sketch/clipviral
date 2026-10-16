# 🚀 Deployment Guide — from zero to a live website (FREE)

Read this like a recipe: do **Part 1 → Part 6 in order**. Every command is ready to copy-paste.
You need: a computer with a terminal (Mac: "Terminal", Windows: "PowerShell"), and internet.

> Words you'll see:
> - **Terminal / command line**: a black (or white) window where you type commands.
> - **Repository (repo)**: a folder on GitHub that holds your code.
> - **Environment variables / env vars / secrets**: secret settings like passwords (API keys).

---

## PART 1 — Create a GitHub account and upload the code

### 1.1 Make a GitHub account (2 minutes)

1. Go to **https://github.com** → click **Sign up**.
2. Enter your email, make a password, choose a username. Done.

### 1.2 Upload this project to GitHub

Open your terminal and run these commands **one line at a time**.

First, tell GitHub who you are (use YOUR name and email):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Then go into the project folder and save the code to GitHub:

```bash
cd opusclip-clone
git init
git add .
git commit -m "ClipViral - AI video clipping SaaS"
git branch -M main
```

Now create the repo on GitHub. **Easiest way (no extra installs):**

1. Go to **https://github.com/new**
2. Repository name: `clipviral`
3. Choose **Private** (recommended) → click **Create repository**.
4. GitHub shows you a page with commands. Copy the two lines that look like this and run them in your terminal (replace `YOUR-USERNAME` with your real GitHub username):

```bash
git remote add origin https://github.com/YOUR-USERNAME/clipviral.git
git push -u origin main
```

GitHub will ask for your username and password. **Use a "Personal Access Token", not your password:**
1. Go to **https://github.com/settings/tokens** → **Generate new token (classic)**.
2. Check the box `repo` → **Generate** → copy the `ghp_...` token.
3. When the terminal asks for a password, paste that token.

✅ Check: refresh your GitHub page — you should see the folders `backend`, `frontend`, `supabase`.

---

## PART 2 — Get your FREE AI key (Groq) — costs $0, no credit card

This is the "brain" of the app (it writes transcripts and finds viral moments).
We use **Groq** because it is **free forever** and needs **no payment method**.

1. Go to **https://console.groq.com** → **Sign Up** (you can sign up with your Google or GitHub account).
2. In the left menu click **API Keys** → **Create API Key**.
3. Name it `clipviral` → **Submit**.
4. **Copy the key now** (it starts with `gsk_...`). It is shown only once — save it in a notes app.

✅ You now have: `GROQ_API_KEY = gsk_...`

> 🔼 **Optional upgrade for later (not needed now):** if you ever want the paid OpenAI models
> (Whisper-1 + GPT-4o), get a key at https://platform.openai.com/api-keys, add billing there,
> then on Render set `AI_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`. The code switches
> automatically — nothing else changes. Skip this for now.

---

## PART 3 — Set up Supabase (database + login + file storage)

1. Go to **https://supabase.com** → **Start your project free** → sign in with GitHub.
2. Click **New project**.
   - Name: `clipviral`
   - Database password: make one up and save it (you won't need it often).
   - Region: pick the one closest to you → **Create new project**. Wait ~2 minutes.
3. **Create the tables**: in the left menu click **SQL Editor** → **New query**.
   - Open the file `supabase/schema.sql` from this project on your computer, copy EVERYTHING,
     paste it into the big box → click **Run**. You should see "Success. No rows returned".
4. **Make logins easy (for testing)**: left menu → **Authentication** → **Providers** → **Email**:
   - Turn **OFF** "Confirm email" (so you can log in without clicking a confirmation email).
   - Click **Save**.
5. **Get your keys**: left menu → **Project Settings** (gear icon) → **API**. Copy these 3 values:
   - **Project URL** → looks like `https://abcdefgh.supabase.co`
   - **anon public** key → long text starting `eyJ...`
   - **service_role** key → another long `eyJ...` ⚠️ keep this one SECRET (backend only!)

✅ You now have: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

---

## PART 4 — Deploy the BACKEND on Render (the brain + FFmpeg)

1. Go to **https://render.com** → **Get Started for Free** → sign in with GitHub.
2. Click **New +** → **Web Service** → **Connect a repository** → allow GitHub → pick `clipviral`.
3. Fill in the form exactly like this:
   - **Name**: `opusclip-api`
   - **Root Directory**: `backend`  ← very important! Type `backend`
   - **Runtime**: **Docker**  ← very important! (this installs FFmpeg for us)
   - **Instance Type**: **Free**
   - Everything else: leave as default.
4. Scroll to **Environment Variables** → click **Add Environment Variable** and add these:

| Key | Value (paste YOURS) |
|---|---|
| `AI_PROVIDER` | `groq` |
| `GROQ_API_KEY` | `gsk_...` (from Part 2) |
| `SUPABASE_URL` | `https://xxxx.supabase.co` (from Part 3) |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` service_role (from Part 3) |
| `SUPABASE_ANON_KEY` | `eyJ...` anon (from Part 3) |
| `CORS_ORIGINS` | `http://localhost:3000` (you'll add your Vercel address in Part 6) |

5. Click **Create Web Service**. The first build takes 5–10 minutes (it's installing FFmpeg + tools).
6. **Test it**: when the status says "Live", open `https://opusclip-api.onrender.com/api/health`
   — you should see `{"status":"ok", ...}`. 🎉

> Note for the future (technical, not urgent): Render's free instance sleeps after ~15 minutes
> without visitors and has 512 MB RAM. First request after sleep takes ~1 minute to wake up.
> Long videos need a paid instance type for comfortable processing. Everything works on free
> for short/medium test videos.

---

## PART 5 — Deploy the FRONTEND on Vercel (the website)

1. Go to **https://vercel.com** → **Sign up** → **Continue with GitHub**.
2. Click **Add New…** → **Project** → find `clipviral` → **Import**.
3. In the import form:
   - **Framework Preset**: Next.js (picked automatically)
   - **Root Directory**: click **Edit** → choose `frontend` ← very important!
4. Before deploying, open **Environment Variables** and add these 3:

| Key | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` (from Part 3) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` anon (from Part 3) |
| `NEXT_PUBLIC_API_URL` | `https://opusclip-api.onrender.com` (your Part 4 address, NO slash at the end) |

5. Click **Deploy**. Wait ~3 minutes. Vercel shows confetti when done. 🎊
6. Click **Visit** — your website is LIVE on `https://clipviral.vercel.app` (or your chosen name).

---

## PART 6 — Connect the two halves (last 2 minutes!)

The backend must accept requests from your new website address:

1. Go back to **Render** → `opusclip-api` → **Environment**.
2. Change `CORS_ORIGINS` to:
   ```
   http://localhost:3000,https://clipviral.vercel.app
   ```
   (use YOUR real Vercel address)
3. Click **Save Changes** → Render rebuilds automatically (~2 minutes).

---

## ✅ Final test (the happy path)

1. Open your Vercel website → **Sign up** with your email + password.
2. Log in → you land on the **Dashboard**.
3. Drag in a video (use a small one first — under 50 MB — podcasts work great).
4. Watch the status: *listening → finding viral moments → cutting clip #1/2/3…*
5. When it says **Completed**: play the clips and hit **Download 9:16 clip**.

🎬 **That's it. Your AI video clipping SaaS is live.**

---

## 📋 Cheat sheet — every command from this guide

```bash
# --- Git setup (once per computer) ---
git config --global user.name "Your Name"
git config --global user.email "you@example.com"

# --- Upload code to GitHub ---
cd opusclip-clone
git init
git add .
git commit -m "ClipViral - AI video clipping SaaS"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/clipviral.git
git push -u origin main

# --- Local backend test (optional) ---
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# --- Local frontend test (optional) ---
cd frontend
npm install
npm run dev

# --- After future code changes: upload the new version ---
cd opusclip-clone
git add .
git commit -m "Update"
git push
```
(When you `git push`, Render and Vercel automatically rebuild — that's the magic of connecting them.)
