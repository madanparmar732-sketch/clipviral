# 🎬 ClipViral — OpusClip Clone (AI Video Clipping SaaS)

Turn **long videos** into **viral 9:16 short clips with animated captions** — automatically.

> Built for the owner who doesn't code. Every file is complete and ready.
> Just follow **[DEPLOYMENT.md](./DEPLOYMENT.md)** step by step.

---

## What this project is (explained simply)

Imagine a robot video editor:

1. 📥 You give it a **long video** (podcast, webinar, interview).
2. 🎙️ **Whisper** (OpenAI) writes down everything said in the video, word by word, with timing.
3. 🧠 **GPT-4o** (OpenAI) reads that text and picks the **3 most viral moments**.
4. ✂️ **FFmpeg** (a video scissors) cuts those moments and makes them **vertical (9:16)** — the shape TikTok/Reels/Shorts love.
5. 💬 **Animated captions** (popping, word-by-word highlighted) are burned into the video.
6. 📤 The finished clips appear in your **dashboard** with **Download** buttons.

---

## What's inside (the folder map)

```
opusclip-clone/
├── README.md              ← you are here
├── DEPLOYMENT.md          ← how to put it on the internet (follow this!)
├── TROUBLESHOOTING.md     ← fix the 5 most common errors
├── supabase/
│   └── schema.sql         ← the database setup (copy-paste into Supabase)
├── backend/               ← the BRAIN (Python FastAPI + FFmpeg + AI)
│   ├── app/
│   │   ├── main.py            ← the API front door
│   │   ├── config.py          ← settings
│   │   ├── auth.py            ← checks who is logged in
│   │   ├── supabase_client.py ← talks to the database
│   │   ├── routers/           ← the 3 API groups: upload, jobs, clips
│   │   ├── services/          ← Whisper, GPT-4o, captions, FFmpeg, storage
│   │   └── workers/pipeline.py← the magic worker that ties it all together
│   ├── requirements.txt   ← Python ingredients list
│   ├── Dockerfile         ← tells Render how to install FFmpeg
│   ├── render.yaml        ← optional Render blueprint
│   └── .env.example       ← secret keys template (copy to .env)
└── frontend/              ← the WEBSITE (Next.js + Tailwind + Shadcn UI)
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx         ← beautiful landing page
    │   │   ├── login/ signup/   ← account pages
    │   │   └── dashboard/       ← status + downloads page
    │   ├── components/          ← upload box, job cards, UI kit
    │   └── lib/                 ← Supabase + API helpers
    ├── package.json       ← JavaScript ingredients list
    └── .env.example       ← public keys template (copy to .env.local)
```

---

## Tech stack (as requested)

| Job | Tool |
|---|---|
| Website | Next.js (React) + Tailwind CSS + Shadcn UI |
| API / brain | Python **FastAPI** |
| Video cutting | **FFmpeg** + **MoviePy** (MoviePy makes the optional recap reel) |
| Transcription | **Whisper** — via **Groq FREE API** by default (or OpenAI Whisper, one setting) |
| Highlight picking | **GPT-OSS-120B** — via **Groq FREE API** by default (or GPT-4o, one setting) |
| Database & login | **Supabase** (free tier) |
| Hosting | **Vercel** (website) + **Render** (backend) |

> 💰 **Total monthly cost to run: $0.** Every piece has a free tier and the AI engine
> defaults to Groq (free forever, no credit card). OpenAI stays available as an upgrade
> (`AI_PROVIDER=openai`) with zero code changes.

---

## Quick local test (optional — you can skip straight to DEPLOYMENT.md)

**1. Backend** (needs Python 3.10+ and FFmpeg installed on your computer):

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then open .env and paste your keys
uvicorn app.main:app --reload --port 8000
```

**2. Frontend** (in a second terminal):

```bash
cd frontend
npm install
cp .env.example .env.local        # then open .env.local and paste your keys
npm run dev
```

Open **http://localhost:3000** — that's your website.

---

## Next step

➡️ Open **[DEPLOYMENT.md](./DEPLOYMENT.md)** and follow it top to bottom.
If anything breaks, **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** has the fixes.
