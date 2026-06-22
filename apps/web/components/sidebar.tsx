"use client";

import { Activity, Bot, BrainCircuit, Building2, ChevronLeft, ChevronRight, FileChartColumn, GitBranch, LayoutDashboard, MessagesSquare, ScrollText, Settings, ShieldCheck, Sparkles, UserRound, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { DashboardSummary, User } from "@/lib/types";
import { cn } from "@/lib/utils";

export const navigation = [
  ["Dashboard", "/", LayoutDashboard, "main"], ["Leads", "/leads", UserRound, "main"],
  ["Workflows", "/workflows", GitBranch, "main"], ["Approvals", "/approvals", ShieldCheck, "main"],
  ["Communications", "/communications", MessagesSquare, "main"], ["Reports", "/reports", FileChartColumn, "main"],
  ["Agent monitor", "/agents", Bot, "ai"], ["AI Operations", "/ai-ops", BrainCircuit, "ai"],
  ["Audit logs", "/audit", ScrollText, "admin"], ["Users", "/users", Users, "admin"], ["Settings", "/settings", Settings, "admin"],
] as const;

export function Sidebar({ collapsed, onCollapse, me, summary }: { collapsed:boolean; onCollapse:()=>void; me:User|null; summary:DashboardSummary|null }) {
  const pathname = usePathname();
  const visible = navigation.filter(([label,,,group]) => group!=="admin" || me?.role==="admin" || (label==="Audit logs"&&me?.role==="manager"));
  return <aside aria-label="Workspace navigation" className={cn("fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-[#1d2938] bg-[var(--sidebar)] text-slate-300 transition-[width] duration-200 lg:flex",collapsed?"w-[76px]":"w-[248px]")}>
    <div className="flex h-16 items-center gap-3 border-b border-[#1d2938] px-4">
      <Link href="/" aria-label="OrbitOps home" className="flex min-w-0 items-center gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-blue-500 text-white shadow-[0_0_28px_rgba(59,130,246,.28)]"><Sparkles size={18}/></span>{!collapsed&&<span className="truncate"><b className="block text-sm tracking-tight text-white">OrbitOps</b><small className="block text-[10px] font-medium uppercase tracking-[.12em] text-[#75839a]">AI command center</small></span>}</Link>
      <button onClick={onCollapse} aria-label={collapsed?"Expand sidebar":"Collapse sidebar"} className={cn("ml-auto grid size-7 shrink-0 place-items-center rounded-md text-[#75839a] hover:bg-white/5 hover:text-white",collapsed&&"absolute -right-3 top-[74px] border border-[#2c3a4d] bg-[#0d1420]")}>{collapsed?<ChevronRight size={14}/>:<ChevronLeft size={14}/>}</button>
    </div>
    {!collapsed&&<button className="mx-3 mt-3 flex items-center gap-2 rounded-lg border border-[#243247] bg-white/[.025] p-2.5 text-left hover:bg-white/[.05]"><span className="grid size-7 place-items-center rounded-md bg-indigo-500/20 text-indigo-300"><Building2 size={14}/></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold text-white">OrbitOps Demo</span><span className="block text-[10px] text-[#75839a]">Production workspace</span></span><ChevronRight size={13} className="text-[#75839a]"/></button>}
    <nav className="mt-4 flex-1 space-y-0.5 overflow-y-auto px-3">{visible.map(([label,href,Icon,group],index)=>{const active=href==="/"?pathname===href:pathname.startsWith(href);const prev=visible[index-1]?.[3];return <div key={href}>{group!==prev&&!collapsed&&<p className="mb-1 mt-5 px-2 text-[10px] font-bold uppercase tracking-[.14em] text-[#536176] first:mt-0">{group==="main"?"Workspace":group==="ai"?"AI control plane":"Administration"}</p>}<Link title={collapsed?label:undefined} href={href as never} className={cn("group relative flex min-h-9 items-center gap-3 rounded-lg px-2.5 text-[13px] font-medium transition",active?"bg-blue-500/12 text-blue-300":"text-[#8b98ad] hover:bg-white/[.045] hover:text-white",collapsed&&"justify-center px-0")}><Icon size={16}/>{!collapsed&&<span>{label}</span>}{!collapsed&&label==="Approvals"&&Boolean(summary?.pending_approvals)&&<span className="ml-auto rounded-full bg-amber-400/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">{summary?.pending_approvals}</span>}{active&&<span className="absolute inset-y-2 -left-3 w-0.5 rounded-full bg-blue-400"/>}</Link></div>})}</nav>
    {!collapsed&&<div className="mx-3 mb-3 rounded-xl border border-[#243247] bg-white/[.025] p-3"><div className="flex items-center gap-2 text-[11px] font-semibold text-emerald-300"><Activity size={13}/> Systems operational<span className="ml-auto size-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"/></div><p className="mt-1.5 text-[10px] leading-relaxed text-[#75839a]">{summary?`${summary.active_runs} live workflows · ${summary.success_rate}% agent success`:'Syncing platform health…'}</p></div>}
  </aside>;
}
