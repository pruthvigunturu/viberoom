// Onboarding form: collect the user's vibe + interests, POST to the API,
// then navigate to the matches page once the agent run completes.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api } from "../api";
import { Button, Card, Input, Textarea, toast } from "../components/ui";

// Rotating status messages shown while the agent is running. They give the
// user a sense of progress for a request that can take a few seconds.
const LOADING_BEATS = [
  "Reading your vibe…",
  "Searching for matches…",
  "Crafting icebreakers…",
];

export default function Create() {
  // `useNavigate` returns an imperative router function — used to push to
  // /matches/:id once the API call resolves.
  const nav = useNavigate();

  // Local component state (controlled inputs). One useState per field
  // keeps the data flow obvious — no reducer / form library needed at this scale.
  const [name, setName] = useState("");
  const [vibe, setVibe] = useState("");
  const [interestsText, setInterestsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Index into LOADING_BEATS to show the current "thinking" status.
  const [beat, setBeat] = useState(0);

  // While submitting, advance the loading message every 1.5s. The cleanup
  // function clears the interval whenever `submitting` flips back to false
  // (or the component unmounts).
  useEffect(() => {
    if (!submitting) return;
    const id = setInterval(() => setBeat(b => (b + 1) % LOADING_BEATS.length), 1500);
    return () => clearInterval(id);
  }, [submitting]);

  // Cheap client-side validity check. The backend re-validates with Pydantic.
  const valid = name.trim() && vibe.trim().length >= 10 && interestsText.trim();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault(); // stop default browser form submission/page reload
    if (!valid || submitting) return;
    setSubmitting(true);
    setBeat(0);
    try {
      // Split the comma-separated interests into a clean string[]. Trimming
      // and filtering empties keeps "music, , coding" from producing junk.
      const interests = interestsText.split(",").map(i => i.trim()).filter(Boolean);
      const result = await api.createUser({ name: name.trim(), vibe_text: vibe.trim(), interests });
      // Push to matches page using the freshly-created user's id.
      nav(`/matches/${result.user.id}`);
    } catch (err) {
      console.error(err);
      // `err instanceof Error` narrows the unknown caught value safely.
      toast(err instanceof Error ? err.message : "Something went wrong.");
      // Re-enable the form so the user can retry.
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

          {/* Submit button doubles as the loading indicator. */}
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
