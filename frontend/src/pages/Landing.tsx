// Marketing landing page. Pure presentation — no API calls, no state.
import { Link } from "react-router-dom";
import { ArrowRight, Brain, Fingerprint, MessageCircle, Users } from "lucide-react";
import { Card } from "../components/ui";

// "How it works" copy, mirroring the four LangGraph nodes in the backend
// agent. Keeping this list adjacent to the JSX makes it easy for a junior
// engineer to update text without diving into the rendering logic.
const STEPS = [
  { icon: Brain, title: "We read your vibe", body: "An LLM extracts your mood, energy, and key themes from a paragraph." },
  { icon: Fingerprint, title: "We make a fingerprint", body: "HuggingFace embeddings turn your vibe into a 384-dim vector." },
  { icon: Users, title: "We find your people", body: "Semantic search across the community ranks the closest vibes." },
  { icon: MessageCircle, title: "We break the ice", body: "Personalized openers, generated for each match in parallel." },
];

export default function Landing() {
  return (
    <div className="max-w-5xl mx-auto px-6 pt-10 pb-20">
      {/* Hero: big headline + CTA → /create */}
      <section className="text-center pt-12 pb-16">
        <h1 className="text-5xl md:text-6xl font-semibold tracking-tight text-stone-900 leading-tight">
          Find your people.<br />
          {/* `bg-clip-text` + transparent text creates the gradient text effect. */}
          <span className="bg-gradient-to-r from-rose-500 to-amber-500 bg-clip-text text-transparent">
            Skip the small talk.
          </span>
        </h1>
        <p className="mt-6 text-lg text-stone-600 max-w-xl mx-auto">
          Most matchmaking is filters. We do it on vibe — describe yours in plain English and an AI agent finds the conversations worth having.
        </p>
        <Link
          to="/create"
          className="inline-flex items-center gap-2 mt-8 rounded-xl bg-rose-500 text-white px-6 py-3 text-base font-medium shadow-lg shadow-rose-200 hover:bg-rose-600 transition"
        >
          Start your vibe <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* "How it works" — one Card per agent step. */}
      <section>
        <h2 className="text-center text-sm uppercase tracking-widest text-stone-500 mb-6">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {STEPS.map((s, i) => {
            // Capitalise the icon component name so JSX treats it as a component
            // rather than a lowercase HTML element.
            const Icon = s.icon;
            return (
              // `!p-5` overrides Card's default `p-6` (Tailwind's `!` = important).
              <Card key={s.title} className="!p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="rounded-xl bg-rose-100 text-rose-600 p-2">
                    <Icon className="w-5 h-5" />
                  </div>
                  {/* Step number, zero-padded for alignment. */}
                  <span className="text-xs text-stone-400 tabular-nums">0{i + 1}</span>
                </div>
                <h3 className="font-semibold text-stone-900 mb-1">{s.title}</h3>
                <p className="text-sm text-stone-600 leading-relaxed">{s.body}</p>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}
