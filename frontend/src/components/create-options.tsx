"use client";

/**
 * OpusClip-parity create options — everything OpusClip lets you tune before
 * clipping, we let you tune too (and it all stays FREE).
 * Persists to localStorage; api.ts attaches it to every upload / link import.
 */

import { useEffect, useState } from "react";
import { ChevronDown, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getCreateOptions, listBrandKits, saveCreateOptions, type BrandKit, type CreateOptions } from "@/lib/api";

const GENRES = ["Auto", "Podcast", "Education", "Entertainment", "Gaming", "Sports", "News", "Business", "Comedy", "Music"];
const ASPECTS = [
  { id: "9:16", label: "📱 Portrait 9:16 (Shorts/Reels/TikTok)" },
  { id: "1:1", label: "⬜ Square 1:1 (Feed)" },
  { id: "16:9", label: "🖥️ Landscape 16:9 (YouTube)" },
];
const LENGTHS: { id: string; lo: number; hi: number; label: string }[] = [
  { id: "quick", lo: 0, hi: 30, label: "⚡ ≤30s" },
  { id: "standard", lo: 0, hi: 45, label: "🎬 ≤45s" },
  { id: "long", lo: 30, hi: 90, label: "📜 30–90s" },
];

export default function CreateOptions() {
  const [open, setOpen] = useState(false);
  const [genre, setGenre] = useState("Auto");
  const [keywords, setKeywords] = useState("");
  const [prompt, setPrompt] = useState("");
  const [length, setLength] = useState("standard");
  const [aspect, setAspect] = useState("9:16");
  const [fillers, setFillers] = useState(false);
  const [censor, setCensor] = useState(false);
  const [lang, setLang] = useState("");
  const [webhook, setWebhook] = useState("");
  const [brandKit, setBrandKit] = useState("");
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const o = getCreateOptions();
    if (o.genre) setGenre(o.genre);
    if (o.topic_keywords?.length) setKeywords(o.topic_keywords.join(", "));
    if (o.custom_prompt) setPrompt(o.custom_prompt);
    if (o.aspect) setAspect(o.aspect);
    if (o.remove_fillers) setFillers(true);
    if (o.auto_censor) setCensor(true);
    if (o.source_lang) setLang(o.source_lang);
    if (o.webhook_url) setWebhook(o.webhook_url);
    if (o.brand_kit_id) setBrandKit(o.brand_kit_id);
    const d = o.clip_durations?.[0];
    if (d) {
      const m = LENGTHS.find((l) => l.lo === d[0] && l.hi === d[1]);
      if (m) setLength(m.id);
    }
    (async () => {
      try {
        const { createClient } = await import("@/lib/supabase/client");
        const { data: { session } } = await createClient().auth.getSession();
        if (session) {
          const r = await listBrandKits(session.access_token);
          setKits(r.brand_kits || []);
        }
      } catch {
        /* brand kits optional */
      }
    })();
  }, []);

  function persist() {
    const len = LENGTHS.find((l) => l.id === length) || LENGTHS[1];
    const opts: CreateOptions = {
      genre: genre === "Auto" ? "" : genre,
      topic_keywords: keywords.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 8),
      custom_prompt: prompt.trim(),
      clip_durations: [[len.lo, len.hi]],
      aspect,
      remove_fillers: fillers,
      auto_censor: censor,
      source_lang: lang.trim(),
      webhook_url: webhook.trim(),
      brand_kit_id: brandKit,
    };
    saveCreateOptions(opts);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium"
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-violet-400" />
          Pro controls — genre, keywords, length, aspect & more
          <Badge variant="secondary" className="text-[10px]">FREE</Badge>
        </span>
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="space-y-4 border-t border-white/10 px-4 pb-4 pt-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Genre</Label>
              <select
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm"
              >
                {GENRES.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Topic keywords (comma se)</Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g. cricket, politics, motivation"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Custom prompt (AI ko exactly kya dhoondhna hai)</Label>
            <Input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. find funny fails and shocking reveals only"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {LENGTHS.map((l) => (
              <Button
                key={l.id}
                type="button"
                size="sm"
                variant={length === l.id ? "default" : "outline"}
                onClick={() => setLength(l.id)}
              >
                {l.label}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            {ASPECTS.map((a) => (
              <Button
                key={a.id}
                type="button"
                size="sm"
                variant={aspect === a.id ? "default" : "outline"}
                onClick={() => setAspect(a.id)}
              >
                {a.label}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex cursor-pointer items-center gap-2">
              <input type="checkbox" checked={fillers} onChange={(e) => setFillers(e.target.checked)} className="accent-violet-500" />
              🧹 Remove filler words (um, uh, like…)
            </label>
            <label className="flex cursor-pointer items-center gap-2">
              <input type="checkbox" checked={censor} onChange={(e) => setCensor(e.target.checked)} className="accent-violet-500" />
              🔇 Auto-bleep swears
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Source language (optional, ISO code)</Label>
              <Input value={lang} onChange={(e) => setLang(e.target.value)} placeholder="e.g. hi, en, es — blank = auto" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Webhook URL (job complete pe ping)</Label>
              <Input value={webhook} onChange={(e) => setWebhook(e.target.value)} placeholder="https://… (optional)" />
            </div>
          </div>

          {kits.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-xs">Brand kit</Label>
              <select
                value={brandKit}
                onChange={(e) => setBrandKit(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm"
              >
                <option value="">— koi nahi —</option>
                {kits.map((k) => (
                  <option key={k.id} value={k.id}>{k.name}</option>
                ))}
              </select>
            </div>
          )}

          <Button size="sm" onClick={persist}>
            {saved ? "✅ Saved — ab upload/link use karega" : "Save options"}
          </Button>
        </div>
      )}
    </div>
  );
}
