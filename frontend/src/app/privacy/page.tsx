import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How ClipViral collects, uses and protects your data.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16 text-white">
      <h1 className="mb-2 text-4xl font-black">Privacy Policy</h1>
      <p className="mb-8 text-white/50">Last updated: October 2026</p>

      <div className="space-y-6 leading-relaxed text-white/80">
        <p>
          ClipViral (&quot;we&quot;, &quot;us&quot;) provides a free AI video clip generator. This policy explains what
          data we collect and how we use it. By using ClipViral you agree to this policy.
        </p>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">1. What we collect</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li><b>Account data</b> — your email address and name from Google Sign-In.</li>
            <li><b>Content you upload</b> — videos/links you submit, the clips we generate, and transcripts. Stored securely to provide the service and deleted automatically after a short retention period.</li>
            <li><b>Usage data</b> — pages visited, features used, browser type, and error logs, to keep the service running and improve it.</li>
            <li><b>Cookies</b> — a session cookie keeps you signed in. Advertising cookies (Google AdSense) may be used to show ads; see section 4.</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">2. How we use it</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li>To provide the service: download your source video, transcribe it, generate clips and captions.</li>
            <li>To send service emails (job finished, errors). We never spam.</li>
            <li>To prevent abuse (rate limits, fraud).</li>
          </ul>
          <p className="mt-2">We do <b>not</b> sell your personal data.</p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">3. Storage &amp; security</h2>
          <p>
            Data is stored on Supabase (authentication + storage) and Render (processing servers). Videos are stored
            in private cloud storage and are deleted automatically within 24 hours (clips you keep live in your
            account until deletion). Access is limited to the service itself.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">4. Advertising</h2>
          <p>
            ClipViral is free and supported by ads. Google AdSense may use cookies to serve ads based on your prior
            visits to this or other websites. Google&apos;s use of advertising cookies enables it and its partners to
            serve ads based on your visits. You can opt out of personalised advertising at{" "}
            <a className="text-purple-300 underline" href="https://www.google.com/settings/ads" target="_blank" rel="noreferrer">Google Ads Settings</a>.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">5. Your rights</h2>
          <p>
            You can request deletion of your account and data at any time by contacting us. You can also request a
            copy of your data. We respond within 30 days.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">6. Children</h2>
          <p>ClipViral is not directed at children under 13. We do not knowingly collect data from children.</p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-white">7. Changes &amp; contact</h2>
          <p>
            We may update this policy; the date above shows the latest version. Questions? Visit our{" "}
            <Link className="text-purple-300 underline" href="/contact">contact page</Link>.
          </p>
        </section>
      </div>
    </main>
  );
}
