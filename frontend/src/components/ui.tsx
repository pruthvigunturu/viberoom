// Tiny, dependency-free UI kit. Every primitive (Card, Button, Input...)
// is a thin wrapper around a native element with Tailwind classes baked
// in for visual consistency.
//
// We intentionally avoid a full component library (shadcn/Radix/MUI)
// here because:
//   * The component count is small.
//   * It keeps the bundle tiny.
//   * It's a great teaching surface — every "design token" is one
//     Tailwind class away.
import { useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";

// Class-merging helper. Accepts any number of string|false|null|undefined
// values and joins the truthy ones with spaces. Lets us write things like
//   cx("base-class", isActive && "active-class", props.className)
type Cx = (string | false | null | undefined)[];
const cx = (...c: Cx) => c.filter(Boolean).join(" ");

/** Rounded panel with a soft pink shadow — the canvas for most content. */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-2xl bg-white/90 backdrop-blur shadow-sm shadow-rose-100/40 border border-rose-100 p-6", className)}>
      {children}
    </div>
  );
}

/**
 * Multi-variant button. Spreads any extra `<button>` props through, so
 * callers can still set `onClick`, `disabled`, `type`, etc.
 */
export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "secondary" }) {
  // Shared styles every variant inherits.
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  // `as const` narrows the value types so TS knows `variants[variant]` is a string.
  const variants = {
    primary: "bg-rose-500 text-white hover:bg-rose-600 active:bg-rose-700 shadow shadow-rose-200",
    secondary: "bg-white text-stone-700 border border-stone-200 hover:bg-stone-50",
    ghost: "bg-transparent text-rose-600 hover:bg-rose-50",
  } as const;
  return (
    <button className={cx(base, variants[variant], className)} {...props}>
      {children}
    </button>
  );
}

/** Native <input> with our standard rounded/focus styling. */
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cx(
        "w-full rounded-xl border border-stone-200 bg-white px-3.5 py-2.5 text-sm text-stone-800 placeholder:text-stone-400",
        "focus:outline-none focus:ring-2 focus:ring-rose-300 focus:border-rose-300 transition",
        props.className,
      )}
    />
  );
}

/** Native <textarea> — same look as Input but with `resize-none`. */
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cx(
        "w-full rounded-xl border border-stone-200 bg-white px-3.5 py-2.5 text-sm text-stone-800 placeholder:text-stone-400",
        "focus:outline-none focus:ring-2 focus:ring-rose-300 focus:border-rose-300 transition resize-none",
        props.className,
      )}
    />
  );
}

/** Pill label used for moods, themes, interests. Three colour tones. */
export function Badge({ children, tone = "rose", className }: { children: ReactNode; tone?: "rose" | "amber" | "stone"; className?: string }) {
  const tones = {
    rose: "bg-rose-100 text-rose-700 border-rose-200",
    amber: "bg-amber-100 text-amber-700 border-amber-200",
    stone: "bg-stone-100 text-stone-700 border-stone-200",
  } as const;
  return (
    <span className={cx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border", tones[tone], className)}>
      {children}
    </span>
  );
}

/** Visualises the LLM's `energy_level` (1–10) as a horizontal gradient bar. */
export function EnergyBar({ value, max = 10 }: { value: number; max?: number }) {
  // `Math.min/max` clamps the percentage into [0, 100] so an unexpected
  // value from the API can never blow out the layout.
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
        <span>Energy</span>
        {/* `tabular-nums` keeps digits the same width so the value doesn't jitter as it changes. */}
        <span className="tabular-nums">{value}/{max}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-stone-100 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber-400 via-rose-400 to-rose-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny in-house toast system.
//
// We avoid a dependency by implementing the smallest possible pub/sub:
//   * Module-level `_toasts` array holds the active toasts.
//   * `_listeners` is a Set of React setState functions, one per ToastHost.
//   * `toast(msg)` mutates `_toasts` and notifies every listener.
//   * `ToastHost` subscribes on mount, unsubscribes on unmount.
// ---------------------------------------------------------------------------
type Toast = { id: number; message: string };
let _toastId = 0;
const _listeners = new Set<(toasts: Toast[]) => void>();
let _toasts: Toast[] = [];
function _emit() { _listeners.forEach(l => l(_toasts)); }

/** Show a toast for ~2.2s. Call from anywhere; no React context needed. */
export function toast(message: string) {
  const t = { id: ++_toastId, message };
  _toasts = [..._toasts, t];
  _emit();
  // Auto-dismiss. We replace the array (not mutate) so React sees a new ref.
  setTimeout(() => {
    _toasts = _toasts.filter(x => x.id !== t.id);
    _emit();
  }, 2200);
}

/**
 * Renders the toast stack. Mount once near the root of the app (see
 * `main.tsx`). Multiple hosts would all show the same toasts.
 */
export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  useEffect(() => {
    // Subscribe on mount, unsubscribe on unmount.
    _listeners.add(setToasts);
    return () => { _listeners.delete(setToasts); };
  }, []);
  return (
    // `pointer-events-none` on the wrapper lets clicks pass through the
    // empty space; each toast re-enables them so its own click works.
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map(t => (
        <div key={t.id} className="pointer-events-auto rounded-xl bg-stone-800 text-white text-sm px-4 py-2 shadow-lg animate-in fade-in">
          {t.message}
        </div>
      ))}
    </div>
  );
}
