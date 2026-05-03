import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import { ToastHost } from "./components/ui";
import Landing from "./pages/Landing";
import Create from "./pages/Create";
import Matches from "./pages/Matches";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Landing />} />
          <Route path="create" element={<Create />} />
          <Route path="matches/:userId" element={<Matches />} />
        </Route>
      </Routes>
    </BrowserRouter>
    <ToastHost />
  </StrictMode>,
);
