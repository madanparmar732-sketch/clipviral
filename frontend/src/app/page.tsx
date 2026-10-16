import Link from "next/link";
import AdSlot from "@/components/ad-slot";
import {
  ArrowRight,
  Captions,
  Clapperboard,
  Download,
  Gauge,
  Scissors,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";

import Navbar from "@/components/navbar";
import UploadDropzone from "@/components/upload-dropzone";
import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    icon: Wand2,
    title: "AI highlight detection",
    text: "GPT-4o reads your entire transcript and pinpoints the 3 most viral moments — hooks, punchlines, big emotions.",
  },
  {
    icon: Scissors,
    title: "Automatic 9:16 reframing",
    text: "FFmpeg cuts each moment and centers it in perfect vertical format for TikTok, Reels and Shorts.",
  },
  {
    icon: Captions,
    title: "Animated captions",
    text: "Word-by-word captions pop and highlight in sync with the speech — the style that stops the scroll.",
  },
  {
    icon: Gauge,
    title: "Virality score",
    text: "Every clip gets a 1–100 score and a ready-to-post hook title, so you know what to publish first.",
  },
  {
    icon: Download,
    title: "One-click downloads",
    text: "Finished clips land in your dashboard with instant download buttons — no watermarks.",
  },
  {
    icon: ShieldCheck,
    title: "Your videos, your account",
    text: "Secure login and private project history, powered by Supabase. Only you see your library.",
  },
];

const STEPS = [
  {
    step: "01",
    title: "Upload a long video",
    text: "Drag in a podcast, webinar, interview, coaching call or stream VOD.",
  },
  {
    step: "02",
    title: "AI does the editing",
    text: "Whisper transcribes, GPT-4o finds the gold, FFmpeg cuts & captions it.",
  },
  {
    step: "03",
    title: "Download & post",
    text: "Grab your 9:16 clips with hook titles and hashtags, and publish.",
  },
];

function PhoneMockup() {
  return (
    <div className="relative mx-auto w-64 animate-float">
      {/* phone frame */}
      <div className="rounded-[2.5rem] border border-white/15 bg-gradient-to-b from-white/10 to-white/5 p-3 shadow-2xl shadow-violet-500/20">
        <div className="relative aspect-[9/16] overflow-hidden rounded-[2rem] bg-gradient-to-b from-violet-950 via-slate-900 to-cyan-950">
          {/* fake speaker face block */}
          <div className="absolute inset-x-10 top-16 h-40 rounded-3xl bg-gradient-to-br from-violet-500/40 to-cyan-400/30" />
          <div className="absolute left-1/2 top-24 h-16 w-16 -translate-x-1/2 rounded-full bg-gradient-to-br from-amber-200/80 to-orange-300/70" />

          {/* animated caption line */}
          <div className="absolute inset-x-4 bottom-24 text-center">
            <p className="text-xl font-black uppercase leading-tight tracking-wide text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)]">
              THIS <span className="text-yellow-300">CHANGES</span> EVERYTHING
            </p>
          </div>

          {/* engagement rail */}
          <div className="absolute bottom-6 right-4 space-y-3 text-center text-white/80">
            <div className="mx-auto h-9 w-9 rounded-full border border-white/20 bg-white/10" />
            <div className="mx-auto h-9 w-9 rounded-full border border-white/20 bg-white/10" />
            <div className="mx-auto h-9 w-9 rounded-full border border-white/20 bg-white/10" />
          </div>

          {/* score chip */}
          <div className="absolute left-4 top-4 rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-bold text-white">
            🔥 92 VIRAL SCORE
          </div>
        </div>
      </div>

      {/* floating side cards */}
      <div className="glass absolute -left-16 top-10 hidden rounded-xl px-4 py-3 text-xs shadow-xl md:block">
        <p className="font-semibold text-white">Clip 1 of 3 ready</p>
        <p className="text-muted-foreground">9:16 · captions burned in</p>
      </div>
      <div className="glass absolute -right-14 bottom-16 hidden rounded-xl px-4 py-3 text-xs shadow-xl md:block">
        <p className="font-semibold text-cyan-300">Whisper ✓ GPT-4o ✓ FFmpeg ✓</p>
        <p className="text-muted-foreground">Processing complete</p>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="hero-glow min-h-screen">
      <Navbar />

      {/* ---------------- HERO ---------------- */}
      <section className="container grid items-center gap-12 pb-20 pt-16 md:grid-cols-2 md:pt-24">
        <div className="animate-fade-in">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-4 py-1.5 text-sm text-violet-200">
            <Sparkles className="h-4 w-4" />
            AI-powered video clipping — powered by GPT-4o & Whisper
          </div>

          <h1 className="text-4xl font-extrabold leading-tight tracking-tight md:text-6xl">
            Turn long videos into{" "}
            <span className="gradient-text">viral shorts</span> on autopilot
          </h1>

          <p className="mt-6 max-w-xl text-lg text-muted-foreground">
            Upload a podcast, webinar or interview. Our AI finds the best moments, cuts them into
            vertical 9:16 clips, and burns animated captions in — ready for TikTok, Reels and Shorts.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link href="/signup">
              <Button size="lg" className="px-8">
                Start clipping free <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="#upload">
              <Button size="lg" variant="outline">
                Try with your video
              </Button>
            </Link>
          </div>

          <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted-foreground">
            <span>✓ 3 viral clips per video</span>
            <span>✓ Animated word-by-word captions</span>
            <span>✓ No editing skills needed</span>
          </div>
        </div>

        <div className="animate-fade-in">
          <PhoneMockup />
        </div>
      </section>

      {/* ---------------- STATS STRIP ---------------- */}
      <section className="border-y border-white/10 bg-white/[0.03]">
        <div className="container grid grid-cols-2 gap-8 py-10 text-center md:grid-cols-4">
          {[
            ["9:16", "auto-reframed output"],
            ["3", "AI-picked clips per upload"],
            ["1080p", "full HD downloads"],
            ["100%", "automated captions"],
          ].map(([big, small]) => (
            <div key={small}>
              <p className="text-3xl font-bold gradient-text">{big}</p>
              <p className="mt-1 text-sm text-muted-foreground">{small}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- FEATURES ---------------- */}
      <section id="features" className="container py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold md:text-4xl">
            Everything you need to <span className="gradient-text">go viral</span>
          </h2>
          <p className="mt-4 text-muted-foreground">
            One upload in, a folder of scroll-stopping shorts out. No timeline editing, no keyframes.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-2xl border border-white/10 bg-white/5 p-7 transition-all hover:-translate-y-1 hover:border-violet-400/40 hover:bg-white/10"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-cyan-400/20">
                <feature.icon className="h-6 w-6 text-violet-300" />
              </div>
              <h3 className="text-lg font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- HOW IT WORKS ---------------- */}
      <section id="how-it-works" className="border-y border-white/10 bg-white/[0.03] py-24">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold md:text-4xl">How it works</h2>
            <p className="mt-4 text-muted-foreground">Three steps. Zero editing experience needed.</p>
          </div>

          <div className="mt-14 grid gap-8 md:grid-cols-3">
            {STEPS.map((item) => (
              <div key={item.step} className="relative rounded-2xl border border-white/10 bg-card p-8">
                <span className="text-5xl font-black text-white/10">{item.step}</span>
                <h3 className="mt-4 text-xl font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- AD (Google AdSense when enabled) ---------------- */}
      <section className="container pb-8">
        <AdSlot slot="landing-mid" />
      </section>

      {/* ---------------- UPLOAD / CTA ---------------- */}
      <section id="upload" className="container py-24">
        <div className="mx-auto max-w-3xl rounded-3xl border border-violet-400/20 bg-gradient-to-b from-violet-500/10 to-cyan-400/5 p-10 text-center">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-cyan-400">
            <Clapperboard className="h-7 w-7 text-white" />
          </div>
          <h2 className="text-3xl font-bold">Ready? Drop your first video</h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
            Sign up takes 20 seconds. Then drag in a video and watch the AI turn it into shorts.
          </p>
          <div className="mx-auto mt-8 max-w-xl text-left">
            <UploadDropzone compact />
          </div>
        </div>
      </section>

      {/* ---------------- FOOTER ---------------- */}
      <footer className="border-t border-white/10 py-10">
        <div className="container flex flex-col items-center justify-between gap-4 text-sm text-muted-foreground md:flex-row">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-cyan-400">
              <Clapperboard className="h-4 w-4 text-white" />
            </span>
            <span className="font-semibold text-foreground">
              Clip<span className="gradient-text">Viral</span>
            </span>
          </div>
          <p>Built with Next.js, FastAPI, Supabase, Whisper &amp; GPT-4o.</p>
          <div className="flex gap-6">
            <Link href="/#features" className="hover:text-foreground">Features</Link>
            <Link href="/login" className="hover:text-foreground">Log in</Link>
            <Link href="/signup" className="hover:text-foreground">Sign up</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
