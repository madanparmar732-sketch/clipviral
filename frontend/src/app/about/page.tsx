import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About Us",
  description: "ClipViral — the free OpusClip alternative. Why we built it and who it's for.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16 text-foreground">
      <h1 className="mb-6 text-4xl font-black">About ClipViral</h1>

      <div className="space-y-6 leading-relaxed text-foreground/80">
        <p className="text-xl text-foreground">
          ClipViral is a <b>100% free AI video clip generator</b> — an OpusClip alternative that doesn&apos;t put your
          best features behind a paywall.
        </p>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">Why we built it</h2>
          <p>
            Every creator deserves viral-ready clips. Tools like OpusClip are great — but their free plans are tiny and
            the real features are locked behind subscriptions. We think that&apos;s backwards. So ClipViral gives you{" "}
            <b>everything free</b>: unlimited videos, all 20 caption styles, auto-captions, filler-word removal,
            smart reframing, sound effects, colour grading and a full editor. Pro only removes ads and the watermark
            and adds a speed boost — it never locks features.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">How it works</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li><b>AI watches your video</b> — transcription finds every word, then picks the most viral moments.</li>
            <li><b>Auto-clip</b> — each moment becomes a vertical short with animated captions, reframed to faces.</li>
            <li><b>Live editor</b> — edit captions in your browser with instant preview, or fine-tune with the studio-grade re-render editor.</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">Who it&apos;s for</h2>
          <p>
            Podcasters, YouTubers, educators, coaches, marketers and small businesses who want Shorts, Reels and
            TikToks from their long videos — without editing skills and without paying ₹2,000/month.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">Our promise</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li>Free means free — no watermarks on your content beyond a tiny logo on the free plan, no feature gates.</li>
            <li>Your content is yours. We delete your source videos automatically after processing.</li>
            <li>We&apos;re independent and bootstrapped — funded by unobtrusive ads and the optional Pro plan.</li>
          </ul>
        </section>

        <p>
          Ready? <Link className="text-purple-300 underline" href="/dashboard">Generate your first clips free</Link>{" "}
          or see <Link className="text-purple-300 underline" href="/pricing">what Pro adds</Link>.
        </p>
      </div>
    </main>
  );
}
