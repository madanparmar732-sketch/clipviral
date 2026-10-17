import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms and conditions for using ClipViral.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16 text-foreground">
      <h1 className="mb-2 text-4xl font-black">Terms of Service</h1>
      <p className="mb-8 text-muted-foreground">Last updated: October 2026</p>

      <div className="space-y-6 leading-relaxed text-foreground/80">
        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">1. The service</h2>
          <p>
            ClipViral is a free AI tool that turns long videos into short clips with captions. All core features are
            free. An optional Pro plan removes ads and the watermark and adds priority processing.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">2. Your content</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li>You keep all rights to the videos you upload.</li>
            <li>You must own the video or have permission from the owner to use it.</li>
            <li>You grant us a limited licence to store and process your videos to produce your clips.</li>
            <li>Do not upload illegal content, copyrighted material without permission, nudity, hate or violence.</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">3. Acceptable use</h2>
          <p>
            Don&apos;t abuse the service: no automated scraping, no reselling of the free service, no attempts to break
            or overload the platform. We may limit or suspend accounts that harm the service or other users.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">4. Pro plan &amp; refunds</h2>
          <p>
            Pro is billed as a simple subscription (₹299). It removes ads and the watermark and puts your jobs in the
            priority queue. If Pro doesn&apos;t work for you, contact us within 7 days for a full refund.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">5. Copyright / DMCA</h2>
          <p>
            We respect copyright. If you believe content on ClipViral infringes your copyright, contact us with the
            details and we will remove it promptly.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">6. Disclaimer</h2>
          <p>
            The service is provided &quot;as is&quot;. We work hard to keep it running but we don&apos;t guarantee
            uninterrupted availability or that every clip will be perfect. AI transcription can make mistakes —
            always review your clips before posting.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-xl font-bold text-foreground">7. Contact</h2>
          <p>
            Questions about these terms? <Link className="text-purple-300 underline" href="/contact">Contact us</Link>.
          </p>
        </section>
      </div>
    </main>
  );
}
