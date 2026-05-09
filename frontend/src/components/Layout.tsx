// Persistent app shell: header + main content slot + footer.
// React Router renders the active page into <Outlet />.
import { Link, NavLink, Outlet } from "react-router-dom";
import { Sparkles } from "lucide-react"; // icon library — tree-shaken at build time

export default function Layout() {
  return (
    // Tailwind utility classes only. The gradient is the app's visual
    // signature — keep it consistent across pages.
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-rose-50 to-orange-50">
      {/* Sticky header. `backdrop-blur` + translucent bg gives a frosted
          glass effect when content scrolls behind it. */}
      <header className="sticky top-0 z-10 backdrop-blur bg-white/70 border-b border-rose-100">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          {/* Logo links to home. `Link` is React Router's client-side <a>. */}
          <Link to="/" className="flex items-center gap-2 text-rose-600 font-semibold text-lg">
            <Sparkles className="w-5 h-5" />
            VibeRoom
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            {/* `NavLink` is `Link` with active-state styling. The `end`
                prop on "/" prevents it being marked active for every
                sub-route. */}
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `transition ${isActive ? "text-rose-600 font-medium" : "text-stone-500 hover:text-stone-800"}`
              }
            >
              Home
            </NavLink>
            <NavLink
              to="/create"
              className={({ isActive }) =>
                `transition ${isActive ? "text-rose-600 font-medium" : "text-stone-500 hover:text-stone-800"}`
              }
            >
              Find your people
            </NavLink>
          </nav>
        </div>
      </header>
      {/* Active page renders here. Defined by the <Route> children in main.tsx. */}
      <main>
        <Outlet />
      </main>
      <footer className="max-w-5xl mx-auto px-6 py-10 text-xs text-stone-400 text-center">
        LangGraph · Groq · HuggingFace · ChromaDB
      </footer>
    </div>
  );
}
