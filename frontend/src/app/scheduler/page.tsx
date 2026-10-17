"use client";

/**
 * Scheduler & Collections — OpusClip's social scheduling + collections, free.
 * Schedule posts per platform, export the calendar (.ics), organise clips.
 */

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, Download, FolderPlus, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import {
  createCollection, deleteCollection, deleteSchedule, listCollections,
  listSchedules, type Collection, type Schedule,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SchedulerPage() {
  const [token, setToken] = useState("");
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [newCol, setNewCol] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"schedule" | "collections">("schedule");

  const load = useCallback(async (t: string) => {
    try {
      const [s, c] = await Promise.all([listSchedules(t), listCollections(t)]);
      setSchedules(s.schedules || []);
      setCollections(c.collections || []);
    } catch {
      /* first load before login */
    }
  }, []);

  useEffect(() => {
    createClient()
      .auth.getSession()
      .then(({ data: { session } }) => {
        if (session) {
          setToken(session.access_token);
          load(session.access_token);
        }
      });
  }, [load]);

  async function addCollection() {
    if (!newCol.trim() || !token) return;
    setBusy(true);
    try {
      await createCollection(token, newCol.trim());
      setNewCol("");
      await load(token);
    } finally {
      setBusy(false);
    }
  }

  async function removeCol(id: string) {
    await deleteCollection(token, id);
    await load(token);
  }

  async function removeSched(id: string) {
    await deleteSchedule(token, id);
    await load(token);
  }

  function exportIcs() {
    fetch(`${API_URL}/api/schedules.ics`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((b) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = "clipviral-schedule.ics";
        a.click();
        URL.revokeObjectURL(a.href);
      });
  }

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">📅 Scheduler & Collections</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Schedule posts, export a calendar, and organize clips into collections.
          </p>
        </div>
        <Link href="/dashboard" className="text-sm text-accent hover:underline">
          ← Dashboard
        </Link>
      </div>

      <div className="flex gap-2">
        <Button size="sm" variant={tab === "schedule" ? "default" : "outline"} onClick={() => setTab("schedule")}>
          📅 Scheduled posts ({schedules.length})
        </Button>
        <Button size="sm" variant={tab === "collections" ? "default" : "outline"} onClick={() => setTab("collections")}>
          📁 Collections ({collections.length})
        </Button>
      </div>

      {tab === "schedule" && (
        <section className="space-y-3">
          <Button size="sm" variant="outline" onClick={exportIcs} disabled={!token}>
            <Download className="h-4 w-4" /> Calendar export (.ics)
          </Button>
          {schedules.length === 0 && (
            <p className="rounded-xl border border-border p-6 text-center text-sm text-muted-foreground">
              Abhi koi schedule nahi. Clip card ke <b>More tools</b> se social copy banao → <b>Schedule</b> dabao.
            </p>
          )}
          {schedules.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-xl border border-border p-4">
              <div>
                <div className="flex items-center gap-2">
                  <Badge>{s.platform}</Badge>
                  <span className="text-sm font-medium">{s.title || "Scheduled clip"}</span>
                </div>
                <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <CalendarDays className="h-3.5 w-3.5" />
                  {new Date(s.publish_at).toLocaleString()}
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => removeSched(s.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </section>
      )}

      {tab === "collections" && (
        <section className="space-y-3">
          <div className="flex gap-2">
            <Input value={newCol} onChange={(e) => setNewCol(e.target.value)} placeholder="Collection ka naam (e.g. Best hooks)" />
            <Button onClick={addCollection} disabled={busy || !newCol.trim()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FolderPlus className="h-4 w-4" />} Add
            </Button>
          </div>
          {collections.length === 0 && (
            <p className="rounded-xl border border-border p-6 text-center text-sm text-muted-foreground">
              No collections yet — name one above to create it, then add clips from any clip card.
            </p>
          )}
          {collections.map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-xl border border-border p-4">
              <div>
                <p className="text-sm font-medium">📁 {c.name}</p>
                <p className="text-xs text-muted-foreground">{(c.clip_ids || []).length} clips</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => removeCol(c.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
