"use client";

import { ArrowLeft, ExternalLink, KeyRound, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiConnectionBadge } from "@/components/ApiConnectionBadge";
import {
  clearCursorApiKey,
  fetchSettings,
  getApiBaseUrl,
  updateCursorApiKey,
} from "@/lib/api";
import type { CursorApiKeyStatus } from "@/lib/types";

function formatUpdatedAt(value: string | null): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleString();
}

export default function SettingsPage() {
  const [status, setStatus] = useState<CursorApiKeyStatus | null>(null);
  const [newKey, setNewKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchSettings();
      setStatus(data.cursor_api_key);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load settings";
      setError(`${message} → ${getApiBaseUrl()}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!newKey.trim()) {
      setError("Enter a Cursor API key before saving.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateCursorApiKey(newKey.trim());
      setStatus(updated);
      setNewKey("");
      setSuccess("Cursor API key saved. New jobs will use this account immediately.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save API key");
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    if (!window.confirm("Remove the stored Cursor API key? New jobs will fail until a key is set.")) {
      return;
    }
    setClearing(true);
    setError(null);
    setSuccess(null);
    try {
      await clearCursorApiKey();
      setStatus({
        configured: false,
        masked_preview: null,
        updated_at: null,
      });
      setSuccess("Cursor API key cleared.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear API key");
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="app-shell">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="top-bar shrink-0">
          <div className="flex min-w-0 items-center gap-2">
            <Link href="/" className="icon-btn" aria-label="Back to dashboard">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-sm font-semibold">Settings</h1>
              <p className="text-[11px] text-zinc-500">Platform configuration</p>
            </div>
          </div>
        </div>

        <div className="workspace-scroll px-4 py-5 lg:px-8">
          <div className="mx-auto w-full max-w-xl space-y-5">
            <section className="glass-panel rounded-2xl p-5">
              <div className="mb-4 flex items-start gap-3">
                <div className="rounded-xl bg-accent/20 p-2 text-accent-glow">
                  <KeyRound className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold">Cursor API key</h2>
                  <p className="mt-1 text-xs text-zinc-400">
                    Switch Cursor accounts without restarting the VPS. Agent containers read the key
                    from disk when each job starts.
                  </p>
                </div>
              </div>

              {loading ? (
                <p className="text-sm text-zinc-500">Loading…</p>
              ) : (
                <>
                  <div className="mb-4 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-zinc-500">Status</span>
                      <span
                        className={
                          status?.configured
                            ? "text-emerald-300"
                            : "text-amber-300"
                        }
                      >
                        {status?.configured ? "Configured" : "Not configured"}
                      </span>
                    </div>
                    {status?.configured && status.masked_preview && (
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="text-zinc-500">Current key</span>
                        <code className="font-mono text-zinc-300">{status.masked_preview}</code>
                      </div>
                    )}
                    {status?.updated_at && (
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="text-zinc-500">Updated</span>
                        <span className="text-zinc-400">{formatUpdatedAt(status.updated_at)}</span>
                      </div>
                    )}
                  </div>

                  <form onSubmit={(event) => void handleSave(event)} className="space-y-3">
                    <label className="block text-xs text-zinc-400" htmlFor="cursor-api-key">
                      New API key
                    </label>
                    <input
                      id="cursor-api-key"
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      value={newKey}
                      onChange={(event) => setNewKey(event.target.value)}
                      placeholder="Paste key from Cursor dashboard"
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-zinc-100 outline-none ring-accent/40 placeholder:text-zinc-600 focus:ring-2"
                    />
                    <div className="flex flex-wrap gap-2">
                      <button type="submit" className="btn-primary" disabled={saving}>
                        {saving ? "Saving…" : "Save key"}
                      </button>
                      <button
                        type="button"
                        className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-zinc-300 transition hover:bg-white/[0.08]"
                        disabled={clearing || !status?.configured}
                        onClick={() => void handleClear()}
                      >
                        {clearing ? "Clearing…" : "Clear key"}
                      </button>
                    </div>
                  </form>
                </>
              )}
            </section>

            <section className="rounded-2xl border border-sky-500/20 bg-sky-500/5 px-4 py-3 text-xs text-sky-100/90">
              <div className="mb-2 flex items-center gap-2 font-medium text-sky-200">
                <ShieldCheck className="h-4 w-4" />
                Hot reload — no VPS reboot
              </div>
              <ul className="list-disc space-y-1 pl-5 text-sky-100/80">
                <li>Saving updates the agent env file immediately.</li>
                <li>The next queued job uses the new Cursor account.</li>
                <li>Running jobs keep the key they started with.</li>
                <li>No orchestrator-api or VPS restart is required.</li>
              </ul>
            </section>

            <p className="text-xs text-zinc-500">
              Generate or rotate keys at{" "}
              <a
                href="https://cursor.com/dashboard?tab=settings"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-accent-glow hover:underline"
              >
                cursor.com/dashboard
                <ExternalLink className="h-3 w-3" />
              </a>
            </p>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
                {success}
              </div>
            )}
          </div>
        </div>
      </main>

      <ApiConnectionBadge compact />
    </div>
  );
}
