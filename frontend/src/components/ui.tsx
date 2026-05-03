import { useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";

type Cx = (string | false | null | undefined)[];
const cx = (...c: Cx) => c.filter(Boolean).join(" ");

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-2xl bg-white/90 backdrop-blur shadow-sm shadow-rose-100/40 border border-rose-100 p-6", className)}>
      {children}
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "secondary" }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
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

export function EnergyBar({ value, max = 10 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
        <span>Energy</span>
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

// Tiny toast
type Toast = { id: number; message: string };
let _toastId = 0;
const _listeners = new Set<(toasts: Toast[]) => void>();
let _toasts: Toast[] = [];
function _emit() { _listeners.forEach(l => l(_toasts)); }

export function toast(message: string) {
  const t = { id: ++_toastId, message };
  _toasts = [..._toasts, t];
  _emit();
  setTimeout(() => {
    _toasts = _toasts.filter(x => x.id !== t.id);
    _emit();
  }, 2200);
}

export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  useEffect(() => {
    _listeners.add(setToasts);
    return () => { _listeners.delete(setToasts); };
  }, []);
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map(t => (
        <div key={t.id} className="pointer-events-auto rounded-xl bg-stone-800 text-white text-sm px-4 py-2 shadow-lg animate-in fade-in">
          {t.message}
        </div>
      ))}
    </div>
  );
}
