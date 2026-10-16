"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldAlert, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Ad slot for FREE users:
 * 1) Detects adblockers (bait element) -> friendly "ads keep it free" wall.
 * 2) Shows Google AdSense if NEXT_PUBLIC_ADSENSE_ID is set (paste your ID later).
 * 3) Otherwise shows a house ad promoting Pro (converting ads > pennies!).
 */
export default function AdSlot({ compact = false }: { compact?: boolean }) {
  const [blocked, setBlocked] = useState(false);
  const adSenseId = process.env.NEXT_PUBLIC_ADSENSE_ID;

  useEffect(() => {
    // Bait: adblockers usually hide/remove elements with this class name.
    const check = () => {
      const bait = document.getElementById("ad-bait");
      if (!bait) return setBlocked(true);
      const style = window.getComputedStyle(bait);
      if (bait.offsetHeight === 0 || style.display === "none" || style.visibility === "hidden") {
        setBlocked(true);
      }
    };
    const t = setTimeout(check, 600);
    return () => clearTimeout(t);
  }, []);

  if (blocked) {
    return (
      <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
          <div>
            <p className="text-sm font-semibold text-amber-300">Adblocker detected 🚫</p>
            <p className="mt-1 text-xs text-amber-200/80">
              Ads keep ClipViral FREE for everyone. Please disable your adblocker for this site — or go Pro
              and enjoy zero ads, no watermark and all 20 caption styles.
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
    <div className={compact ? "py-2" : "py-3"}>
      {/* bait element for adblock detection — looks like a tiny empty ad */}
      <div id="ad-bait" className="ad-banner adsbox h-1 w-1 overflow-hidden opacity-0" />

      {adSenseId ? (
        <ins
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={adSenseId}
          data-ad-slot="auto"
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
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
