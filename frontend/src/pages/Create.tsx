import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api } from "../api";
import { Button, Card, Input, Textarea, toast } from "../components/ui";

const LOADING_BEATS = [
  "Reading your vibe…",
  "Searching for matches…",
  "Crafting icebreakers…",
];

export default function Create() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [vibe, setVibe] = useState("");
  const [interestsText, setInterestsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [beat, setBeat] = useState(0);

  useEffect(() => {
    if (!submitting) return;
    const id = setInterval(() => setBeat(b => (b + 1) % LOADING_BEATS.length), 1500);
    return () => clearInterval(id);
  }, [submitting]);

  const valid = name.trim() && vibe.trim().length >= 10 && interestsText.trim();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setBeat(0);
    try {
      const interests = interestsText.split(",").map(i => i.trim()).filter(Boolean);
      const result = await api.createUser({ name: name.trim(), vibe_text: vibe.trim(), interests });
      nav(`/matches/${result.user.id}`);
    } catch (err) {
      console.error(err);
      toast(err instanceof Error ? err.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 pt-12 pb-20">
      <Card className="!p-8">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-rose-100 text-rose-600 mb-3">
            <Sparkles className="w-6 h-6" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-stone-900">Tell us your vibe</h1>
          <p className="text-stone-500 mt-1">We'll find your people.</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label className="text-sm font-medium text-stone-700 block mb-1.5">Name</label>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Maya"
              disabled={submitting}
              autoFocus
            />
          </div>
          <div>
            <label className="text-sm font-medium text-stone-700 block mb-1.5">What's your vibe?</label>
            <Textarea
              rows={4}
              value={vibe}
              onChange={e => setVibe(e.target.value)}
              placeholder="I'm into late-night coding, lo-fi music, and good ramen. Looking for chill conversations about side projects and weird ideas."
              disabled={submitting}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-stone-700 block mb-1.5">Interests</label>
            <Input
              value={interestsText}
              onChange={e => setInterestsText(e.target.value)}
              placeholder="comma-separated, e.g. coding, music, ramen, hiking"
              disabled={submitting}
            />
          </div>

          <Button type="submit" disabled={!valid || submitting} className="w-full !py-3">
            {submitting ? LOADING_BEATS[beat] : "Find my people"}
          </Button>
          {submitting && (
            <p className="text-xs text-stone-400 text-center">
              First request can take a moment — we're warming up the model.
            </p>
          )}
        </form>
      </Card>
    </div>
  );
}
