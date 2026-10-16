import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact Us",
  description: "Get in touch with the ClipViral team — support, feedback, copyright and business enquiries.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16 text-white">
      <h1 className="mb-6 text-4xl font-black">Contact Us</h1>

      <div className="space-y-6 leading-relaxed text-white/80">
        <p>
          We read every message and usually reply within 24–48 hours.
        </p>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
          <h2 className="mb-2 text-xl font-bold text-white">📧 Email</h2>
          <p>
            For support, feedback, copyright (DMCA) and business enquiries, email us at{" "}
            <a href="mailto:support@clipviral.app" className="text-purple-300 underline">
              support@clipviral.app
            </a>
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
          <h2 className="mb-2 text-xl font-bold text-white">🛠️ Support tips</h2>
          <ul className="ml-5 list-disc space-y-1">
            <li>Tell us which page/feature has the problem.</li>
            <li>Include the video link or job ID if it&apos;s about processing.</li>
            <li>A screenshot helps us fix things 10× faster.</li>
          </ul>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
          <h2 className="mb-2 text-xl font-bold text-white">⚖️ Copyright</h2>
          <p>
            If you believe content generated through ClipViral infringes your copyright, email{" "}
            <a href="mailto:support@clipviral.app" className="text-purple-300 underline">support@clipviral.app</a> with
            the URL, proof of ownership and your contact details. We remove infringing content promptly.
          </p>
        </div>
      </div>
    </main>
  );
}
