import { redirect } from "next/navigation";

import Navbar from "@/components/navbar";
import DashboardClient from "@/components/dashboard-client";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login?next=/dashboard");
  }

  return (
    <main className="min-h-screen hero-glow">
      <Navbar />
      <div className="container py-10">
        <DashboardClient userEmail={user.email ?? ""} />
      </div>
    </main>
  );
}
