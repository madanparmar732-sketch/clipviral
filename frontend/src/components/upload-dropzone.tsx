"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Film, Loader2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { createClient } from "@/lib/supabase/client";
import { uploadVideo } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_MB = 512;
const ACCEPTED = [".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"];

export default function UploadDropzone({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [percent, setPercent] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickFile = useCallback((chosen: File | null) => {
    setError(null);
    if (!chosen) return;
    const dotIndex = chosen.name.lastIndexOf(".");
    const ext = dotIndex > 0 ? chosen.name.slice(dotIndex).toLowerCase() : "";
    if (!ACCEPTED.includes(ext)) {
      setError(`Please choose a video file (${ACCEPTED.join(", ")}).`);
      return;
    }
    if (chosen.size > MAX_MB * 1024 * 1024) {
      setError(`That file is over ${MAX_MB} MB. Please use a smaller video.`);
      return;
    }
    setFile(chosen);
  }, []);

  async function startUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setPercent(0);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login?next=/dashboard");
        return;
      }
      await uploadVideo(file, session.access_token, setPercent);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="w-full">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!busy) pickFile(e.dataTransfer.files?.[0] ?? null);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed border-white/20 bg-white/5 text-center transition-all hover:border-violet-400/60 hover:bg-white/10",
          dragging && "scale-[1.01] border-violet-400 bg-violet-500/10",
          compact ? "p-8" : "p-14",
          busy && "pointer-events-none opacity-80"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />

        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/30 to-cyan-400/30">
          {busy ? (
            <Loader2 className="h-8 w-8 animate-spin text-violet-300" />
          ) : (
            <UploadCloud className="h-8 w-8 text-violet-300" />
          )}
        </div>

        <div>
          <p className="text-lg font-semibold">
            {file ? file.name : "Drag & drop your long video here"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {file
              ? `${(file.size / 1024 / 1024).toFixed(1)} MB ready to clip`
              : `or click to browse — MP4, MOV, WEBM, MKV — up to ${MAX_MB} MB`}
          </p>
        </div>

        {file && !busy && (
          <div className="flex items-center gap-2 text-sm text-cyan-300">
            <Film className="h-4 w-4" /> Video selected — press the button below
          </div>
        )}
      </div>

      {busy && (
        <div className="mt-4 space-y-2">
          <Progress value={percent} />
          <p className="text-center text-sm text-muted-foreground">
            Uploading… {percent}% (the AI magic starts right after)
          </p>
        </div>
      )}

      {error && (
        <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="mt-6 flex justify-center">
        <Button size="lg" onClick={startUpload} disabled={!file || busy}>
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Uploading…
            </>
          ) : (
            <>Clip my video ✂️</>
          )}
        </Button>
      </div>
    </div>
  );
}
