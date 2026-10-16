import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClipViral — AI Video Clipping SaaS",
  description:
    "Upload long videos and get viral 9:16 short clips with animated captions — automatically.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
