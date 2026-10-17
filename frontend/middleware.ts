import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Runs before every page request. Two jobs:
 * 1. Keep the Supabase login fresh.
 * 2. Guard the dashboard: no login = go to the login page.
 */
/** Side effect: poke the Render API so it never sleeps (sleeping = video
 *  renders dying mid-job). Best-effort: per warm instance we ping once every
 *  4 minutes. Guarded so it can never throw into a page load. */
const API = process.env.NEXT_PUBLIC_API_URL || "https://clipviral-r5m1.onrender.com";
let lastWarm = 0;
function keepRenderWarm() {
  const now = Date.now();
  if (now - lastWarm < 4 * 60 * 1000) return;
  lastWarm = now;
  try {
    void fetch(`${API}/api/health`, { method: "GET", signal: AbortSignal.timeout(70_000) }).catch(() => {});
  } catch {
    /* never break a page load because of a keep-alive */
  }
}

export async function middleware(request: NextRequest) {
  keepRenderWarm();
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: any }[]) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;
  const isProtected = path.startsWith("/dashboard");

  if (isProtected && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", path);
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
