"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Clapperboard, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";

export default function Navbar() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-xl">
      <div className="container flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#191817]">
            <Clapperboard className="h-5 w-5 text-foreground" />
          </span>
          <span className="text-lg font-bold tracking-tight">
            Clip<span className="gradient-text">Viral</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 rounded-full border border-border bg-[#f2efe9] p-1 text-sm md:flex">
          <Link href="/#features" className="rounded-full px-4 py-1.5 text-muted-foreground transition-colors hover:bg-[#f2efe9] hover:text-foreground">Features</Link>
          <Link href="/#how-it-works" className="rounded-full px-4 py-1.5 text-muted-foreground transition-colors hover:bg-[#f2efe9] hover:text-foreground">How it works</Link>
          <Link href="/#upload" className="rounded-full px-4 py-1.5 text-muted-foreground transition-colors hover:bg-[#f2efe9] hover:text-foreground">Try it</Link>
        </nav>

        <div className="flex items-center gap-3">
          {email ? (
            <>
              <Link href="/dashboard">
                <Button variant="secondary" size="sm">Dashboard</Button>
              </Link>
        <Link href="/pricing" className="flex items-center gap-1 rounded-full border border-border bg-[#f2efe9] px-3 py-1.5 text-sm font-semibold text-foreground transition-colors hover:bg-black/[0.04]"><Sparkles className="h-3.5 w-3.5 text-accent" /> Pro</Link>
              <Button variant="ghost" size="sm" onClick={signOut}>
                <LogOut className="h-4 w-4" /> Sign out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost" size="sm">Log in</Button>
              </Link>
              <Link href="/signup">
                <Button size="sm">Get started free</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
