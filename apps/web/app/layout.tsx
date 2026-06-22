import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: { default: "OrbitOps", template: "%s · OrbitOps" },
  description: "Approval-first agentic business operations",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:`document.documentElement.dataset.theme=localStorage.getItem('orbitops-theme')||'dark'`}}/></head><body><AppShell>{children}</AppShell></body></html>;
}
