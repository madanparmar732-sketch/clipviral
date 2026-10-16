"use client";

import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase client for the BROWSER (the "front of the shop").
 * Uses the public anon key — safe to expose in the browser.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
