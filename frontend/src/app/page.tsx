import Link from "next/link";
import AdSlot from "@/components/ad-slot";
import {
  ArrowRight,
  Bell,
  CalendarClock,
  Check,
  Clapperboard,
  Download,
  Eye,
  Gauge,
  Languages,
  Layers,
  Link2,
  Scissors,
  ShieldCheck,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";

import Navbar from "@/components/navbar";
import UploadDropzone from "@/components/upload-dropzone";
import { Button } from "@/components/ui/button";

/* ------------------------------------------------------------------ data */

const PLATFORMS = ["YouTube", "TikTok", "Reels", "Shorts", "Facebook", "X / Twitter", "LinkedIn", "Twitch VODs"];

const FEATURES = [
  {
    icon: Wand2,
    title: "HyperFinder™ moment engine",
    text: "A local virality engine scores every second of your video — audio energy, hook patterns, emotion arc, pacing, trend words — then the LLM confirms the winners. Seconds, not minutes.",
    bullets: ["480s of video scanned in ~1s", "Runs on-device, your footage never trains anyone's model", "LLM only double-checks — never watches your whole video"],
  },
  {
    icon: Gauge,
    title: "4-dimension Virality Score",
    text: "Every clip rated 0–99 on Hook · Flow · Value · Trend with per-dimension bars — the same formula the big paid tools use, free here.",
    bullets: ["See WHY a clip scored before you post it", "Sorts your feed so the bangers come first"],
  },
  {
    icon: Sparkles,
    title: "Studio-grade animated captions",
    text: "Word-by-word karaoke captions with highlight colors, pop animations and 20 burned-in styles. Edit any word inline like a doc — the video updates.",
    bullets: ["20 caption styles — ALL free", "Filler-word & dead-air auto cut", "Translate + burn captions in 10+ languages"],
  },
  {
    icon: Layers,
    title: "Face-aware auto reframe",
    text: "Horizontal podcast? Three-person interview? The reframe model keeps the active speaker centered in 9:16 — or pick 1:1 / 16:9 for other platforms.",
    bullets: ["Auto crop follows whoever is talking", "Every aspect ratio, one click each"],
  },
  {
    icon: Download,
    title: "Post-ready everything",
    text: "Hook titles, descriptions, hashtags, SRT/VTT subtitles, AI thumbnails, 6-platform export packs and a built-in scheduler with .ics export.",
    bullets: ["Collections to organize per client/show", "Public share links for your team", "Webhook when clips finish"],
  },
  {
    icon: ShieldCheck,
    title: "Free. Actually free.",
    text: "No credit meter, no trial timer, no watermark hostage-taking. Every feature on this page is unlocked the second you sign up.",
    bullets: ["Unlimited videos & clips", "No card ever asked"],
  },
];

const STEPS = [
  {
    step: "01",
    title: "Drop a link or file",
    text: "Paste a YouTube / podcast / interview link or drag in an MP4. Webinars, lectures, streams, coaching calls — any genre works.",
  },
  {
    step: "02",
    title: "AI does the editing",
    text: "Whisper transcribes in parallel chunks, HyperFinder scores every second, the LLM judges the winners — then FFmpeg cuts, reframes and captions.",
  },
  {
    step: "03",
    title: "Polish & publish",
    text: "Tweak captions in the Studio, pick your clips, export 9:16 packs with titles + hashtags, or schedule them straight to your week.",
  },
];

const COMPARE_ROWS: [string, boolean | string, boolean | string, boolean | string][] = [
  ["Price for full features", "₹0", "₹0 (your time)", "$15–29/mo"],
  ["Credit / minute meter", false, "—", "5–15 min/mo free"],
  ["Auto clip finding", true, false, true],
  ["Virality score + reasons", true, false, "sometimes"],
  ["Word-by-word captions", "20 styles, free", "manual keyframes", "top styles paywalled"],
  ["Editor you control", "transcript + visual", "full NLE", "basic"],
  ["No watermark on free", true, true, false],
  ["Works without install", "browser", "desktop app", "browser"],
];

const FAQS = [
  {
    q: "Is it really free? Where's the catch?",
    a: "Every clipping, captioning and export feature is free with no credits and no video limits. The paid Pro plan (₹299/mo) only removes ads and the small ClipViral watermark and puts you at the front of the render queue. No card is needed to use everything else, forever.",
  },
  {
    q: "Which videos work?",
    a: "Any link from YouTube, podcasts, X, Facebook or Instagram — or upload an MP4/MOV directly. Podcasts, interviews, coaching calls, webinars, gaming VODs, sports analysis and vlogs all work; the finder is genre-aware (sports, news, education, entertainment, promo).",
  },
  {
    q: "How fast do clips come back?",
    a: "Transcription and moment-finding are lightning fast (a 1-hour video is scanned in seconds, not minutes). Rendering is done on a free-tier CPU to keep the price at ₹0, so expect a few minutes per clip — you can close the tab, clips land in your dashboard when ready.",
  },
  {
    q: "What is the Virality Score?",
    a: "Each clip gets four sub-scores — Hook (does the first second stop the scroll), Flow (does pacing hold attention), Value (is there a complete payoff) and Trend (is the topic hot) — combined into one 0–99 number so you know what to post first.",
  },
  {
    q: "Do you train AI on my videos?",
    a: "No. Moment-finding runs on our own compute and is deleted after your export window. Nothing is used to train anything.",
  },
  {
    q: "Can I edit the captions?",
    a: "Yes — open a clip in Studio and fix any word inline, change style, colors, position, emphasis and language, then export. The caption file (SRT/VTT) exports with it.",
  },
];

/* ------------------------------------------------------- small components */

function Marquee({ children }: { children: React.ReactNode }) {
  return (
    <div className="mask-fade-x overflow-hidden">
      <div className="flex w-max gap-4 py-1" style={{ animation: "marquee 34s linear infinite" }}>
        {children}
        {children}
      </div>
    </div>
  );
}

function ViralityRing({ score = 92, size = 92 }: { score?: number; size?: number }) {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(226 24% 16%)" strokeWidth="8" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="url(#vgrad)"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={`${(score / 99) * c} ${c}`}
      />
      <defs>
        <linearGradient id="vgrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(190 95% 50%)" />
          <stop offset="100%" stopColor="hsl(245 85% 67%)" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/* the "clip card" mockup used in the hero + feature blocks */
function ClipCardMock({ className = "" }: { className?: string }) {
  return (
    <div className={`glass relative overflow-hidden rounded-3xl p-5 ${className}`}>
      <div className="flex gap-5">
        {/* phone */}
        <div className="relative aspect-[9/16] w-36 shrink-0 overflow-hidden rounded-[1.4rem] border border-border bg-[#131211]">
          <div className="absolute inset-x-6 top-8 h-24 rounded-2xl bg-black/25" />
          <div className="absolute left-1/2 top-12 h-10 w-10 -translate-x-1/2 rounded-full bg-gradient-to-br from-amber-200/80 to-orange-300/70" />
          <div className="absolute inset-x-2 bottom-11 text-center text-[10px] font-black uppercase leading-snug tracking-wide text-foreground drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
            THIS <span className="rounded bg-yellow-300 px-1 text-black">CHANGES</span> EVERYTHING
          </div>
          <div className="absolute bottom-2 right-2 space-y-1.5">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-5 w-5 rounded-full border border-border bg-black/[0.04]" />
            ))}
          </div>
          <span className="absolute left-2 top-2 rounded-full bg-emerald-500/90 px-2 py-0.5 text-[9px] font-bold text-foreground">
            🔥 92
          </span>
        </div>
        {/* right rail */}
        <div className="flex min-w-0 flex-1 flex-col justify-between py-1">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-accent/80">Clip 1 of 6 · 0:34</p>
            <p className="mt-1 line-clamp-2 text-sm font-bold leading-snug">The one decision that fixed his entire season</p>
          </div>
          <div className="mt-3 space-y-1.5">
            {[
              ["Hook", 96, "bg-foreground"],
              ["Flow", 88, "bg-neutral-700"],
              ["Value", 91, "bg-neutral-800"],
              ["Trend", 84, "bg-fuchsia-400"],
            ].map(([label, v, bar]) => (
              <div key={label as string} className="flex items-center gap-2 text-[10px]">
                <span className="w-9 text-muted-foreground">{label}</span>
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-black/[0.04]">
                  <div className={`h-full rounded-full ${bar}`} style={{ width: `${v}%` }} />
                </div>
                <span className="tabular-nums text-muted-foreground">{v}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5 text-[10px]">
            {["#sports", "#motivation", "#podcast"].map((t) => (
              <span key={t} className="rounded-full border border-border bg-[#f2efe9] px-2 py-0.5 text-accent">
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
          </div>
  );
}

/* --------------------------------------------------------------- the page */

export default function LandingPage() {
  return (
    <main className="hero-glow min-h-screen overflow-x-clip">
      <Navbar />

      {/* ---------------- HERO ---------------- */}
      <section className="relative">
        <div className="dot-grid pointer-events-none absolute inset-0" />
        <div className="container relative grid items-center gap-14 pb-20 pt-16 md:grid-cols-[1.05fr_0.95fr] md:pt-24">
          <div className="animate-fade-in">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/[0.08] px-4 py-1.5 text-sm text-accent">
              <Sparkles className="h-4 w-4" />
              OpusClip-grade clipping — 100% free, no credits
            </div>

            <h1 className="text-4xl font-extrabold leading-[1.05] tracking-tight md:text-6xl">
              Your long videos,
              <br />
              <span className="gradient-text sheen bg-clip-text text-transparent">
                cut for the algorithm
              </span>
              .
            </h1>

            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
              Drop a link or file. ClipViral finds the moments worth posting, cuts them into
              vertical 9:16 shorts, burns animated captions and scores each clip 0–99 for
              virality — every feature free, forever.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link href="/signup">
                <Button size="lg" className="px-8 ">
                  Start clipping free <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="#upload">
                <Button size="lg" variant="outline" className="px-7">
                  <Link2 className="mr-2 h-4 w-4" /> Try with your video
                </Button>
              </Link>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-emerald-600" /> Unlimited videos & clips</span>
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-emerald-600" /> No card, ever</span>
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-emerald-600" /> 20 caption styles free</span>
            </div>
          </div>

          {/* hero visual */}
          <div className="animate-fade-in space-y-5 [animation-delay:120ms]">
            <ClipCardMock />
            <div className="glass flex items-center gap-4 rounded-2xl px-5 py-4">
              <ViralityRing />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">6 clips scored · ready to post</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  47-min podcast → done in 3m 41s, not 6 hours
                </p>
                <div className="bar-eq mt-2 flex h-4 items-end gap-1 text-accent">
                  <span /><span /><span /><span /><span />
                </div>
              </div>
              <Bell className="h-4 w-4 shrink-0 animate-pulse text-accent" />
            </div>
          </div>
        </div>

        {/* platform marquee */}
        <div className="border-y border-border/70 bg-[#f6f4f0] py-5">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground/70">
            Made for every short-form platform & source
          </p>
          <Marquee>
            {PLATFORMS.map((p) => (
              <span key={p} className="rounded-full border border-border bg-[#f2efe9] px-6 py-2 text-sm font-semibold text-muted-foreground">
                {p}
              </span>
            ))}
          </Marquee>
        </div>
      </section>

      {/* ---------------- STATS STRIP ---------------- */}
      <section className="container py-16">
        <div className="grid grid-cols-2 gap-8 text-center md:grid-cols-4">
          {[
            ["~1s", "to scan 8 minutes of video (HyperFinder)"],
            ["10–20", "clips out per upload, typically"],
            ["0–99", "virality score on all 4 dimensions"],
            ["₹0", "for every feature on this page"],
          ].map(([big, small]) => (
            <div key={small}>
              <p className="gradient-text text-4xl font-black md:text-5xl">{big}</p>
              <p className="mx-auto mt-2 max-w-[16ch] text-sm text-muted-foreground">{small}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- FEATURES ---------------- */}
      <section id="features" className="container py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="eyebrow mb-3">The platform</p>
          <h2 className="text-3xl font-bold md:text-5xl">
            A full clipping team, <span className="gradient-text">inside one paste</span>
          </h2>
          <p className="mt-4 text-muted-foreground">
            Finder, editor, captioner, designer, scheduler — the jobs you'd pay a freelancer for, automated.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <div
              key={feature.title}
              className={`card-lift group relative overflow-hidden rounded-2xl border border-border bg-[#f2efe9] p-7 ${i === 0 ? "sm:col-span-2 lg:col-span-1" : ""}`}
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-[#f2efe9]">
                <feature.icon className="h-6 w-6 text-accent" />
              </div>
              <h3 className="text-lg font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.text}</p>
              <ul className="mt-4 space-y-1.5">
                {feature.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2 text-xs text-foreground/70">
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" /> {b}
                  </li>
                ))}
              </ul>
              <div className="pointer-events-none absolute -right-16 -top-16 hidden" />
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- HOW IT WORKS ---------------- */}
      <section id="how-it-works" className="border-y border-border bg-[#f6f4f0] py-24">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <p className="eyebrow mb-3">Workflow</p>
            <h2 className="text-3xl font-bold md:text-5xl">Three steps. Zero timeline.</h2>
          </div>

          <div className="relative mt-14 grid gap-8 md:grid-cols-3">
            {/* connective line */}
            <div className="absolute left-[16%] right-[16%] top-12 hidden h-px bg-border md:block" />
            {STEPS.map((item) => (
              <div key={item.step} className="card-lift relative rounded-2xl border border-border bg-card p-8">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full border border-accent/30 bg-background text-sm font-black text-accent">
                  {item.step}
                </div>
                <h3 className="text-xl font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- SHOWCASE BAND ---------------- */}
      <section className="container grid items-center gap-12 py-24 md:grid-cols-2">
        <div>
          <p className="eyebrow mb-3">Studio</p>
          <h2 className="text-3xl font-bold md:text-4xl">
            Captions that hit like CapCut, edited like a doc
          </h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            Every word is a token you can click. Restyle, re-color, re-time, translate — then export
            the video <i>and</i> the SRT. The transcript view lets you cut a clip by deleting
            sentences instead of scrubbing a timeline.
          </p>
          <ul className="mt-6 space-y-2 text-sm">
            {[
              "20 burned-in caption styles, karaoke highlighting, emojis",
              "Auto filler-word removal (uh / um / you know) — toggleable",
              "Censor-beep any word, AI thumbnail with clickbait title",
              "Translate captions + export per-platform aspect packs",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2 text-foreground/80">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> {t}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap gap-3 text-xs">
            {["Collections", "Share links", "Brand kits", "Scheduler + .ics", "Webhooks", "Duplicate & tweak"].map((c) => (
              <span key={c} className="flex items-center gap-1.5 rounded-full border border-border bg-[#f2efe9] px-3 py-1.5 text-foreground/70">
                {c === "Scheduler + .ics" ? <CalendarClock className="h-3.5 w-3.5 text-accent" /> :
                 c === "Share links" ? <Eye className="h-3.5 w-3.5 text-accent" /> :
                 c === "Collections" ? <Layers className="h-3.5 w-3.5 text-accent" /> :
                 c === "Brand kits" ? <Scissors className="h-3.5 w-3.5 text-accent" /> :
                 c === "Webhooks" ? <Link2 className="h-3.5 w-3.5 text-accent" /> :
                 <Languages className="h-3.5 w-3.5 text-accent" />}
                {c}
              </span>
            ))}
          </div>
        </div>

        <div className="relative">
          <ClipCardMock className="rotate-1" />
          <div className="glass absolute -bottom-6 -left-4 hidden rounded-xl px-4 py-3 text-xs shadow-xl md:block">
            <p className="font-semibold text-accent">HyperFinder: 480s scored in 1.2s</p>
            <p className="text-muted-foreground">top 6 clips auto-ranked</p>
          </div>
        </div>
      </section>

      {/* ---------------- COMPARISON ---------------- */}
      <section className="container pb-24">
        <div className="ring-glow overflow-hidden rounded-3xl border border-border bg-card">
          <div className="grid grid-cols-4 gap-2 border-b border-border bg-[#f2efe9] px-6 py-5 text-sm font-semibold md:px-10">
            <span className="text-muted-foreground">What you get</span>
            <span className="text-center"><span className="gradient-text">ClipViral</span></span>
            <span className="hidden text-center text-muted-foreground sm:block">Editing by hand</span>
            <span className="text-center text-muted-foreground">Paid clipper</span>
          </div>
          {COMPARE_ROWS.map(([label, a, b, c], i) => (
            <div key={label} className={`grid grid-cols-4 items-center gap-2 px-6 py-3.5 text-sm md:px-10 ${i % 2 ? "bg-[#f6f4f0]" : ""}`}>
              <span className="text-foreground/90">{label}</span>
              <Cell v={a} strong />
              <span className="hidden sm:block"><Cell v={b} /></span>
              <Cell v={c} />
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- AD (Google AdSense when enabled) ---------------- */}
      <section className="container pb-8">
        <AdSlot slot="landing-mid" />
      </section>

      {/* ---------------- UPLOAD / CTA ---------------- */}
      <section id="upload" className="container py-20">
        <div className="ring-glow mx-auto max-w-3xl rounded-3xl border border-border bg-card p-8 text-center md:p-12">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#191817]">
            <Clapperboard className="h-7 w-7 text-foreground" />
          </div>
          <h2 className="text-3xl font-bold md:text-4xl">Drop your first video</h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
            Sign-up takes 20 seconds. Paste a link below and watch the AI work.
          </p>
          <div className="mx-auto mt-8 max-w-xl text-left">
            <UploadDropzone compact />
          </div>
        </div>
      </section>

      {/* ---------------- FAQ ---------------- */}
      <section className="container pb-24">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow mb-3 text-center">Questions</p>
          <h2 className="text-center text-3xl font-bold md:text-4xl">Straight answers</h2>
          <div className="mt-10 space-y-3">
            {FAQS.map((f) => (
              <details key={f.q} className="group rounded-2xl border border-border bg-[#f2efe9] px-6 py-4 open:bg-[#efece6]">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-semibold md:text-base">
                  {f.q}
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- FINAL CTA ---------------- */}
      <section className="border-t border-border py-20">
        <div className="container flex flex-col items-center gap-6 text-center">
          <h2 className="max-w-2xl text-3xl font-bold md:text-5xl">
            Stop clipping at 1am.
            <br />
            <span className="gradient-text">Let the machine do the boring part.</span>
          </h2>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/signup">
              <Button size="lg" className="px-9 ">
                Create free account <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button size="lg" variant="ghost" className="px-7">See pricing (₹0)</Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ---------------- FOOTER ---------------- */}
      <footer className="border-t border-border bg-[#f4f2ee] py-12">
        <div className="container grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#191817]">
                <Clapperboard className="h-5 w-5 text-foreground" />
              </span>
              <span className="text-lg font-bold tracking-tight">
                Clip<span className="gradient-text">Viral</span>
              </span>
            </div>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
              Free AI video clip generator — long videos in, virality-scored shorts out.
              Built on Next.js, FastAPI, Whisper &amp; HyperFinder.
            </p>
          </div>
          {[
            { title: "Product", links: [["Features", "/#features"], ["How it works", "/#how-it-works"], ["Pricing", "/pricing"], ["Dashboard", "/dashboard"]] },
            { title: "Account", links: [["Sign up free", "/signup"], ["Log in", "/login"], ["Try it now", "/#upload"]] },
            { title: "Legal", links: [["About", "/about"], ["Privacy", "/privacy"], ["Terms", "/terms"], ["Contact", "/contact"]] },
          ].map((col) => (
            <div key={col.title}>
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{col.title}</p>
              <ul className="mt-3 space-y-2 text-sm">
                {col.links.map(([label, href]) => (
                  <li key={label}>
                    <Link href={href} className="text-muted-foreground transition-colors hover:text-foreground">{label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="container mt-10 flex flex-col items-center justify-between gap-3 border-t border-border/70 pt-6 text-xs text-muted-foreground md:flex-row">
          <p>© {new Date().getFullYear()} ClipViral — every feature free, for every creator.</p>
          <p className="flex items-center gap-1.5"><Gauge className="h-3.5 w-3.5 text-emerald-600" /> Virality Score™ by HyperFinder engine</p>
        </div>
      </footer>
    </main>
  );
}

function Cell({ v, strong = false }: { v: boolean | string; strong?: boolean }) {
  return (
    <span className={`flex items-center justify-center text-center ${strong ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
      {v === true ? (
        <Check className="h-4 w-4 text-emerald-600" />
      ) : v === false ? (
        <X className="h-4 w-4 text-red-600/80" />
      ) : (
        <span className="truncate text-xs md:text-sm">{v}</span>
      )}
    </span>
  );
}
