"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  useEffect(() => {
    const saved = localStorage.getItem("orbitops-theme") as "light" | "dark" | null;
    const next = saved || (document.documentElement.dataset.theme as "light" | "dark") || "dark";
    setTheme(next); document.documentElement.dataset.theme = next;
  }, []);
  function toggle() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    setTheme(next); localStorage.setItem("orbitops-theme", next); document.documentElement.dataset.theme = next;
  }
  return <button onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} className="grid size-9 place-items-center rounded-lg border hairline text-muted transition hover:bg-[var(--surface-subtle)] hover:text-[var(--text-strong)]">{theme === "dark" ? <Sun size={16}/> : <Moon size={16}/>}</button>;
}
