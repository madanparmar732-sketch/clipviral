"use client";

/**
 * OpusClip-parity clip toolkit — duplicate, thumbnails, censor, translate,
 * social pack, scheduling, share link, subtitles, collections. All FREE.
 */

import { useEffect, useState } from "react";
import {
  Check, Copy, Download, FolderPlus, Globe, Image as ImageIcon, Languages,
  Link as LinkIcon, Loader2, MoreHorizontal, Scissors, Share2, Sparkles,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  buildSocialPack, censorClip, collectionItem, createSchedule, duplicateClip,
  downloadSubtitles, getSocialPack, listCollections, makeThumbnails, shareClip,
  translateClip, type Clip, type Collection, type SocialPack,
} from "@/lib/api";

const PLATFORMS = ["youtube", "tiktok", "instagram", "x", "linkedin", "facebook"];

export default function ClipActions({ clip, token }: { clip: Clip; token: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [pack, setPack] = useState<SocialPack | null>(null);
  const [lang, setLang] = useState("hi");
  const [platform, setPlatform] = useState("youtube");
  const [when, setWhen] = useState("");
  const [collections, setCollections] = useState<Collection[]>([]);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    if (!open || !token) return;
    listCollections(token).then((r) => setCollections(r.collections || [])).catch(() => {});
    getSocialPack(token, clip.id).then((r) => {
      if (r.pack && Object.keys(r.pack).length) setPack(r.pack);
    }).catch(() => {});
  }, [open, token, clip.id]);

  async function run(kind: string, fn: () => Promise<string | void>) {
    setBusy(kind);
    setNote(null);
    try {
      const msg = await fn();
      setNote(msg || "✅ Done");
    } catch (e) {
      setNote(`⚠️ ${e instanceof Error ? e.message : "failed"}`);
    } finally {
      setBusy(null);
    }
  }

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(""), 1200);
    });
  }

  return (
    <div className="mt-2">
      <Button size="sm" variant="ghost" className="w-full justify-start gap-2 px-2" onClick={() => setOpen((v) => !v)}>
        <MoreHorizontal className="h-4 w-4" />
        {open ? "Hide tools" : "More tools (free)"}
      </Button>

      {open && (
        <div className="mt-2 space-y-3 rounded-lg border border-white/10 bg-black/20 p-3">
          {note && <p className="text-xs text-muted-foreground">{note}</p>}

          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="outline" disabled={!!busy}
              onClick={() => run("dup", async () => { await duplicateClip(token, clip.id); return "✅ Copy ban gaya — Refresh dabao"; })}>
              {busy === "dup" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Copy className="h-3.5 w-3.5" />} Duplicate
            </Button>
            <Button size="sm" variant="outline" disabled={!!busy}
              onClick={() => run("thumb", async () => { await makeThumbnails(token, clip.id, clip.title || ""); return "🖼️ 3 thumbnails ban rahe — 20s me Refresh"; })}>
              {busy === "thumb" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />} Thumbnails
            </Button>
            <Button size="sm" variant="outline" disabled={!!busy}
              onClick={() => run("censor", async () => { await censorClip(token, clip.id, true); return "🔇 Swears bleep ho rahe — 30s me Refresh"; })}>
              {busy === "censor" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Scissors className="h-3.5 w-3.5" />} Bleep swears
            </Button>
            <Button size="sm" variant="outline"
              onClick={() => run("srt", async () => { await downloadSubtitles(clip, "srt", token); return "📝 SRT downloaded"; })}>
              <Download className="h-3.5 w-3.5" /> SRT
            </Button>
          </div>

          {/* translate */}
          <div className="flex items-center gap-2">
            <Languages className="h-3.5 w-3.5 text-violet-400" />
            <Input value={lang} onChange={(e) => setLang(e.target.value)} className="h-8 w-20 text-xs" placeholder="hi" />
            <Button size="sm" variant="outline" disabled={!!busy}
              onClick={() => run("tr", async () => { await translateClip(token, clip.id, lang, true); return `🌐 ${lang.toUpperCase()} version ban raha — 60s me Refresh`; })}>
              {busy === "tr" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Globe className="h-3.5 w-3.5" />} Translate + burn
            </Button>
          </div>

          {/* share */}
          <Button size="sm" variant="outline" className="w-full" disabled={!!busy}
            onClick={() => run("share", async () => {
              const r = await shareClip(token, clip.id);
              copy(`${window.location.origin}/share/${r.share_id}`, "share");
              return "🔗 Public share link copy ho gaya!";
            })}>
            <Share2 className="h-3.5 w-3.5" /> Share link
          </Button>

          {/* collections */}
          <div className="flex flex-wrap items-center gap-2">
            <FolderPlus className="h-3.5 w-3.5 text-violet-400" />
            {collections.length === 0 && <span className="text-xs text-muted-foreground">Collections: dashboard se banao</span>}
            {collections.map((c) => (
              <Button key={c.id} size="sm" variant="ghost" className="h-7 border border-white/10"
                onClick={() => run(`col-${c.id}`, async () => {
                  await collectionItem(token, c.id, clip.id);
                  return `📁 "${c.name}" me add ho gaya`;
                })}>
                + {c.name}
              </Button>
            ))}
          </div>

          {/* social pack */}
          <div className="space-y-2">
            <Button size="sm" variant="outline" className="w-full" disabled={!!busy}
              onClick={() => run("social", async () => {
                const r = await buildSocialPack(token, clip.id);
                setPack(r.pack);
                return "✍️ Social copy ready — pick a platform below";
              })}>
              {busy === "social" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {pack ? "Regenerate social copy" : "Generate social copy (YT/TikTok/IG/X…)"}
            </Button>

            {pack && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1">
                  {PLATFORMS.filter((p) => pack[p]).map((p) => (
                    <Badge key={p} variant={platform === p ? "default" : "secondary"}
                      className="cursor-pointer text-[10px]" onClick={() => setPlatform(p)}>
                      {p}
                    </Badge>
                  ))}
                </div>
                {pack[platform] && (
                  <div className="space-y-1.5 rounded-md border border-white/10 p-2">
                    <p className="text-xs font-semibold">{pack[platform].title}</p>
                    <p className="text-xs text-muted-foreground">{pack[platform].description}</p>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]"
                        onClick={() => copy(`${pack[platform].title}\n\n${pack[platform].description}`, "copy")}>
                        {copied === "copy" ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />} Copy
                      </Button>
                    </div>
                    <div className="flex items-center gap-1 pt-1">
                      <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)}
                        className="h-7 text-[11px]" />
                      <Button size="sm" variant="outline" className="h-7 text-[11px]" disabled={!!busy || !when}
                        onClick={() => run("sched", async () => {
                          await createSchedule(token, {
                            clip_id: clip.id, platform,
                            publish_at: new Date(when).toISOString(),
                            title: pack[platform].title,
                            description: pack[platform].description,
                          });
                          return "📅 Scheduled! /scheduler pe dikhega + calendar export";
                        })}>
                        {busy === "sched" ? <Loader2 className="h-3 w-3 animate-spin" /> : <LinkIcon className="h-3 w-3" />} Schedule
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
