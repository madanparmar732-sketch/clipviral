"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ShieldAlert, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

/**
 * Ad slot — the money layer:
 * 1) REAL ads: set NEXT_PUBLIC_ADSENSE_ID (ca-pub-...) on Vercel -> Google AdSense
 *    ads render here (script loads + unit pushes automatically).
 * 2) No ID yet: a house ad promoting Pro shows instead (still useful!).
 * 3) Adblockers: bait element detects them -> "ads keep it free / go Pro" wall.
 */
export default function AdSlot({
  slot = "auto",
  compact = false,
  label = "Advertisement",
}: {
  slot?: string;
  compact?: boolean;
  label?: string;
}) {
  const [blocked, setBlocked] = useState(false);
  const pushed = useRef(false);
  const adSenseId = process.env.NEXT_PUBLIC_ADSENSE_ID;

  // --- adblock detector (bait element) ---
  useEffect(() => {
    const check = () => {
      const bait = document.getElementById("ad-bait");
      if (!bait) return setBlocked(true);
      const style = window.getComputedStyle(bait);
      if (bait.offsetHeight === 0 || style.display === "none" || style.visibility === "hidden") {
        setBlocked(true);
      }
    };
    const t = setTimeout(check, 700);
    return () => clearTimeout(t);
  }, []);

  // --- load the REAL AdSense script once + push this unit ---
  useEffect(() => {
    if (!adSenseId || blocked || pushed.current) return;
    if (!document.querySelector("script[data-clipviral-adsense]")) {
      const script = document.createElement("script");
      script.dataset.clipviralAdsense = "1";
      script.async = true;
      script.crossOrigin = "anonymous";
      script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adSenseId}`;
      document.head.appendChild(script);
    }
    const tryPush = () => {
      if (pushed.current) return;
      try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
        pushed.current = true;
      } catch {
        /* script not loaded yet — retried below */
      }
    };
    tryPush();
    const retry = setTimeout(tryPush, 1500);
    return () => clearTimeout(retry);
  }, [adSenseId, blocked]);

  if (blocked) {
    return (
      <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
          <div>
            <p className="text-sm font-semibold text-amber-300">Adblocker detected 🚫</p>
            <p className="mt-1 text-xs text-amber-200/80">
              Ads keep ClipViral FREE for everyone. Please disable your adblocker for this site — or go
              Pro and enjoy zero ads, no watermark and all 20 caption styles.
            </p>
            <Link href="/pricing">
              <Button size="sm" className="mt-3 bg-amber-500 text-black hover:bg-amber-400">
                <Sparkles className="h-4 w-4" /> Go Pro — ₹299/mo
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={compact ? "py-2" : "py-4"}>
      {/* bait element for adblock detection */}
      <div id="ad-bait" className="ad-banner adsbox pub_300x250 h-1 w-1 overflow-hidden opacity-0" />

      {adSenseId ? (
        <>
          <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground/60">{label}</p>
          <ins
            className="adsbygoogle"
            style={{ display: "block", minHeight: 90 }}
            data-ad-client={adSenseId}
            data-ad-slot={slot}
            data-ad-format="auto"
            data-full-width-responsive="true"
          />
        </>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 px-4 py-3">
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-white">Tired of ads?</span> Go Pro — no ads, no watermark,
            20 caption styles, 1080p, priority speed.
          </p>
          <Link href="/pricing">
            <Button size="sm" className="bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white">
              <Sparkles className="h-4 w-4" /> Upgrade — ₹299/mo
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}
