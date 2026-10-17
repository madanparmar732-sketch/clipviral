"use client";

/**
 * Brand kit — logo + caption style + accent colour, burned into every render
 * when selected at create time. (OpusClip "Brand Templates", free.)
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, Palette, Save, Trash2, Upload } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { listBrandKits, saveBrandKit, type BrandKit } from "@/lib/api";

const STYLES = ["beast", "neon", "clean", "bold", "karaoke", "minimal"];

export default function BrandKitPage() {
  const [token, setToken] = useState("");
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [name, setName] = useState("My brand");
  const [style, setStyle] = useState("beast");
  const [accent, setAccent] = useState("#7C3AED");
  const [logoDataUrl, setLogoDataUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async (t: string) => {
    try {
      const r = await listBrandKits(t);
      setKits(r.brand_kits || []);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    createClient()
      .auth.getSession()
      .then(({ data: { session } }) => {
        if (session) {
          setToken(session.access_token);
          load(session.access_token);
        }
      });
  }, [load]);

  function pickLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setLogoDataUrl(String(reader.result || ""));
    reader.readAsDataURL(f);
  }

  async function save() {
    if (!token) return;
    setBusy(true);
    setNote("");
    try {
      await saveBrandKit(token, { name, caption_style: style, accent, logo_data_url: logoDataUrl });
      setNote("✅ Brand kit saved! Ab create-options me ye style auto lag jayega.");
      await load(token);
    } catch (e) {
      setNote(`⚠️ ${e instanceof Error ? e.message : "failed"}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">🎨 Brand kit</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Logo, caption style, accent colour — har clip pe automatically.
          </p>
        </div>
        <Link href="/dashboard" className="text-sm text-accent hover:underline">
          ← Dashboard
        </Link>
      </div>

      <div className="space-y-4 rounded-2xl border border-border p-6">
        <div className="space-y-1.5">
          <Label>Kit naam</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <Label>Caption style</Label>
          <div className="flex flex-wrap gap-2">
            {STYLES.map((s) => (
              <Button key={s} size="sm" variant={style === s ? "default" : "outline"} onClick={() => setStyle(s)}>
                {s}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex items-end gap-4">
          <div className="space-y-1.5">
            <Label>Accent colour</Label>
            <input type="color" value={accent} onChange={(e) => setAccent(e.target.value)}
              className="h-10 w-20 cursor-pointer rounded border border-border bg-transparent" />
          </div>
          <div className="space-y-1.5">
            <Label>Logo (PNG/JPG, chhota rakho)</Label>
            <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border px-4 py-2 text-sm hover:bg-[#f2efe9]">
              <Upload className="h-4 w-4" />
              {logoDataUrl ? "Logo selected ✅" : "Choose a logo"}
              <input type="file" accept="image/*" className="hidden" onChange={pickLogo} />
            </label>
          </div>
        </div>

        <Button onClick={save} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save brand kit
        </Button>
        {note && <p className="text-sm text-muted-foreground">{note}</p>}
      </div>

      {kits.length > 0 && (
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Palette className="h-4 w-4" /> Saved kits
          </h2>
          {kits.map((k) => (
            <div key={k.id} className="flex items-center justify-between rounded-xl border border-border p-4">
              <div>
                <p className="text-sm font-medium">{k.name}</p>
                <p className="text-xs text-muted-foreground">
                  style: {k.caption_style} · accent: <span style={{ color: k.accent }}>{k.accent}</span>
                  {k.logo_url ? " · logo ✓" : ""}
                </p>
              </div>
              <Button size="sm" variant="ghost"
                onClick={async () => {
                  await saveBrandKit(token, { id: k.id, name: k.name, caption_style: k.caption_style, accent: k.accent });
                  setName(k.name || "My brand");
                  setStyle(k.caption_style || "beast");
                  setAccent(k.accent || "#7C3AED");
                }}>
                Use
              </Button>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
