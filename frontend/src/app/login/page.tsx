"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Check, Clapperboard, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (signInError) {
      setError(signInError.message);
      setBusy(false);
      return;
    }
    router.push(next);
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <Button type="submit" className="w-full " disabled={busy}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Log in"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        No account yet?{" "}
        <Link href="/signup" className="text-accent underline-offset-4 hover:underline">
          Sign up free
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="hero-glow grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border/70 bg-[#f6f4f0] p-12 lg:flex">
        <div className="dot-grid pointer-events-none absolute inset-0" />
        <Link href="/" className="relative flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#191817]">
            <Clapperboard className="h-5 w-5 text-foreground" />
          </span>
          <span className="text-lg font-bold tracking-tight">
            Clip<span className="gradient-text">Viral</span>
          </span>
        </Link>

        <div className="relative">
          <h2 className="max-w-md text-3xl font-extrabold leading-tight tracking-tight">
            Your clips are already in the footage. <span className="gradient-text">We just find them.</span>
          </h2>
          <ul className="mt-6 space-y-2.5 text-sm text-muted-foreground">
            {["Virality-scored 9:16 clips in minutes", "Word-by-word animated captions — all 20 styles free", "No credits, no limits, no card"].map((t) => (
              <li key={t} className="flex items-center gap-2.5">
                <Check className="h-4 w-4 shrink-0 text-emerald-600" /> {t}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-muted-foreground/60">
          © {new Date().getFullYear()} ClipViral — free AI clipping for every creator.
        </p>
      </div>

      {/* form panel */}
      <div className="flex items-center justify-center p-6">
        <div className="glass w-full max-w-md rounded-3xl p-8 md:p-10">
          <div className="mb-8 text-center lg:text-left">
            <p className="eyebrow mb-2">Welcome back</p>
            <h1 className="text-3xl font-extrabold tracking-tight">Log in</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">Pick up where you left off — your clips are waiting.</p>
          </div>
          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
