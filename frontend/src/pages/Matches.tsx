import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Copy, RefreshCw, Sparkles, Users } from "lucide-react";
import { api } from "../api";
import type { AgentResult } from "../types";
import { Badge, Button, Card, EnergyBar, toast } from "../components/ui";

export default function Matches() {
  const { userId } = useParams();
  const [data, setData] = useState<AgentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!userId) return;
    try {
      const result = await api.getMatches(userId);
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load matches.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-line */ }, [userId]);

  async function refresh() {
    setRefreshing(true);
    await load();
    toast("Refreshed your matches");
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text).then(() => toast("Copied!"));
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-20 text-center text-stone-500">
        <Sparkles className="w-6 h-6 mx-auto mb-2 text-rose-400 animate-pulse" />
        Loading your vibe…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-xl mx-auto px-6 py-20 text-center">
        <p className="text-rose-600 mb-4">{error ?? "User not found."}</p>
        <Link to="/create" className="text-rose-500 underline">Try again</Link>
      </div>
    );
  }

  const { user, vibe_analysis, matches } = data;

  return (
    <div className="max-w-3xl mx-auto px-6 pt-10 pb-20">
      {/* Vibe analysis */}
      <section className="mb-10">
        <p className="text-xs uppercase tracking-widest text-stone-500 mb-2">Your vibe</p>
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900 mb-4">{user.name}</h1>
        <Card>
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <Badge tone="rose" className="text-sm !px-3 !py-1 capitalize">{vibe_analysis.mood || "—"}</Badge>
            {vibe_analysis.key_themes.map(t => (
              <Badge key={t} tone="amber">{t}</Badge>
            ))}
          </div>
          <EnergyBar value={vibe_analysis.energy_level || 0} />
          {vibe_analysis.summary && (
            <p className="mt-4 text-sm text-stone-600 italic">"{vibe_analysis.summary}"</p>
          )}
        </Card>
      </section>

      {/* Matches */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-stone-500 mb-1">Your matches</p>
            <h2 className="text-xl font-semibold text-stone-900 flex items-center gap-2">
              <Users className="w-5 h-5 text-rose-500" />
              {matches.length > 0 ? `Top ${matches.length}` : "No matches yet"}
            </h2>
          </div>
          <Button variant="secondary" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {matches.length === 0 ? (
          <Card className="text-center text-stone-500">
            You're the first one here. Invite friends to find matches.
          </Card>
        ) : (
          <div className="space-y-4">
            {matches.map(m => (
              <Card key={m.user.id}>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-stone-900">{m.user.name}</h3>
                    <p className="text-sm text-stone-600 italic mt-1">"{m.vibe_analysis?.summary || m.user.vibe_text}"</p>
                  </div>
                  <Badge tone="rose" className="!text-sm !px-3 !py-1 tabular-nums shrink-0">
                    {Math.round(m.similarity_score * 100)}% match
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2 mb-4">
                  {m.user.interests.map(i => (
                    <Badge key={i} tone="stone">{i}</Badge>
                  ))}
                </div>
                <div className="space-y-2 pt-2 border-t border-stone-100">
                  <p className="text-xs uppercase tracking-wider text-stone-500">Icebreakers</p>
                  {m.icebreakers.map((ib, idx) => (
                    <button
                      key={idx}
                      onClick={() => copy(ib)}
                      className="w-full text-left rounded-xl border border-rose-100 bg-rose-50/50 hover:bg-rose-100/60 px-4 py-3 text-sm text-stone-800 transition flex items-start gap-3 group"
                    >
                      <Copy className="w-4 h-4 text-rose-400 mt-0.5 shrink-0 group-hover:text-rose-600" />
                      <span>{ib}</span>
                    </button>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
