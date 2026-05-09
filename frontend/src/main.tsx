// Application entry point. Vite serves `index.html`, which loads this
// file as a module — everything below mounts the React tree into the
// `<div id="root">` placeholder in the HTML.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css"; // Tailwind's compiled styles + tiny global tweaks.
import Layout from "./components/Layout";
import { ToastHost } from "./components/ui";
import Landing from "./pages/Landing";
import Create from "./pages/Create";
import Matches from "./pages/Matches";

// `createRoot` is React 18's concurrent renderer. The `!` after
// `getElementById(...)` tells TypeScript "trust me, this exists" — the
// element is hard-coded in `index.html`.
createRoot(document.getElementById("root")!).render(
  // StrictMode double-invokes effects in dev to surface side-effect bugs.
  // It has no effect in production builds.
  <StrictMode>
    {/* BrowserRouter enables clean URLs (no hash). All <Link>/<NavLink>
        usage downstream depends on this provider being at the top. */}
    <BrowserRouter>
      <Routes>
        {/* Layout renders the persistent header/footer; nested routes
            render inside its <Outlet /> via React Router. */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Landing />} />
          <Route path="create" element={<Create />} />
          {/* `:userId` is a URL parameter read via `useParams` in Matches. */}
          <Route path="matches/:userId" element={<Matches />} />
        </Route>
      </Routes>
    </BrowserRouter>
    {/* ToastHost lives at the top level so any page can call `toast(...)`
        and have the message render in a fixed-position container. */}
    <ToastHost />
  </StrictMode>,
);
