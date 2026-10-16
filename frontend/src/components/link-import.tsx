"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { importFromLink } from "@/lib/api";

export default function LinkImport() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    const trimmed = url.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login?next=/dashboard");
        return;
      }
      await importFromLink(trimmed, session.access_token);
      setUrl("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not fetch that link. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Link2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") start();
            }}
            placeholder="Paste a video link… YouTube, Facebook, X, Instagram"
            className="pl-9"
            disabled={busy}
          />
        </div>
        <Button onClick={start} disabled={busy || !url.trim()}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {busy ? "Fetching…" : "Fetch & Clip"}
        </Button>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
