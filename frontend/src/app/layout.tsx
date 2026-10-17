import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://clipviral-kappa.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: "ClipViral",
  title: {
    default: "ClipViral — Free AI Video Clip Generator for Viral Shorts",
    template: "%s | ClipViral",
  },
  description:
    "Turn long videos into viral 9:16 short clips with animated captions — automatically. Free AI video clipper for YouTube, podcasts and interviews. Paste a video link (YouTube, Facebook, X, Instagram) or upload — get hook-based clips with auto captions, pause removal and a transcript editor.",
  keywords: [
    "AI video clip generator",
    "viral shorts maker",
    "YouTube shorts generator",
    "video to shorts",
    "auto captions video",
    "free video clipper",
    "podcast clip maker",
    "Instagram reels generator",
    "OpusClip alternative",
    "ClipViral",
  ],
  authors: [{ name: "ClipViral" }],
  creator: "ClipViral",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "ClipViral",
    title: "ClipViral — Free AI Video Clip Generator for Viral Shorts",
    description:
      "Turn long videos into viral 9:16 short clips with animated captions — automatically. Paste a link or upload. Free AI video clipper.",
    images: [{ url: "/og-cover.jpg", width: 1200, height: 630, alt: "ClipViral — AI video clip generator" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "ClipViral — Free AI Video Clip Generator for Viral Shorts",
    description: "Turn long videos into viral 9:16 short clips with animated captions — automatically. Free AI video clipper.",
    images: ["/og-cover.jpg"],
  },
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
  verification: {
    google: "vc6vLygvBzxrNHMachenIJL7NsiAsZolCVKPOSFdSkA",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "ClipViral",
  url: "/",
  applicationCategory: "MultimediaApplication",
  operatingSystem: "Web",
  description:
    "Free AI video clip generator: turn long videos into viral 9:16 short clips with animated captions, automatic pause removal and a transcript-based editor. Works with YouTube, Facebook, X and Instagram links or direct uploads.",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  featureList: [
    "AI viral moment detection",
    "Animated karaoke captions",
    "Automatic pause removal",
    "Transcript-based clip editor",
    "Video link import (YouTube, Facebook, X, Instagram)",
    "Face-aware 9:16 reframing",
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">

        {children}
        <footer className="border-t border-border bg-background px-6 py-8 text-center text-sm text-muted-foreground">
          <div className="mb-2 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
            <Link href="/about" className="hover:text-foreground">About</Link>
            <Link href="/pricing" className="hover:text-foreground">Pricing</Link>
            <Link href="/privacy" className="hover:text-foreground">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-foreground">Terms of Service</Link>
            <Link href="/contact" className="hover:text-foreground">Contact</Link>
          </div>
          <p>© {new Date().getFullYear()} ClipViral — free AI video clips for everyone.</p>
        </footer>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </body>
    </html>
  );
}
