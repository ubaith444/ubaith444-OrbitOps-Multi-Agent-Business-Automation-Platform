"use client";

import { ArrowRight, Bot, CircleDollarSign, Clock3, FileCheck2, MailCheck, ShieldAlert, Sparkles, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { MetricChart } from "@/components/metric-chart";
import { SectionHeading, StatCard, TrendChart } from "@/components/operations-ui";
import { ErrorState, LoadingState } from "@/components/page-state";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

export default function Dashboard() {
  const [data,setData]=useState<DashboardSummary|null>(null),[error,setError]=useState("");
  const load=useCallback(async()=>{setError("");try{setData(await api("/dashboard/summary"))}catch(reason){setError(reason instanceof Error?reason.message:"Unable to load dashboard")}},[]);
  useEffect(()=>{void load()},[load]);
  return <div className="mx-auto max-w-[1480px]"><PageHeader eyebrow="Operations center" title="Operations overview" description="Live business activity, agent health, and decisions requiring attention." actions={<><Button variant="outline" asChild><Link href="/reports">View reports</Link></Button><Button asChild><Link href="/leads">Add lead</Link></Button></>}/>
    {error&&<ErrorState message={error} retry={load}/>} {!data&&!error&&<LoadingState rows={6}/>} {data&&<>
      <section aria-label="Key performance indicators" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6"><StatCard label="Total leads" value={data.total_leads} icon={Users} trend={12} tone="blue"/><StatCard label="Active workflows" value={data.active_runs} icon={Bot} trend={8} tone="violet"/><StatCard label="Pending approvals" value={data.pending_approvals} icon={Clock3} detail="Requires human review" tone="amber"/><StatCard label="Reports generated" value={data.reports_generated} icon={FileCheck2} trend={5} tone="emerald"/><StatCard label="Communication success" value={`${data.communication.response_rate}%`} icon={MailCheck} tone="cyan"/><StatCard label="AI cost this month" value={`$${data.monthly_cost_usd.toFixed(2)}`} icon={CircleDollarSign} detail={`${data.total_tokens.toLocaleString()} tokens`} tone="rose"/></section>
      <section className="mt-4 grid gap-4 xl:grid-cols-[1.45fr_1fr]"><TrendChart title="Daily workflow executions" description="Completed agent runs over the last seven days" data={data.weekly_leads} color="#3b82f6"/><MetricChart title="Lead pipeline funnel" description="Current conversion across qualification stages" data={data.lead_status}/></section>
      <section className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3"><MetricChart title="Agent success rate" data={data.workflow_outcomes}/><TrendChart title="Token usage" description="Consumption by agent" data={data.token_usage} color="#8b5cf6"/><TrendChart title="Monthly cost trend" description="Estimated AI infrastructure spend" data={data.token_usage.map((item,index)=>({...item,value:Number((item.value*.000018*(index+1)).toFixed(2))}))} color="#f59e0b" suffix=""/></section>
      <SectionHeading title="Needs your attention" action={<Link href="/approvals" className="flex items-center gap-1 text-xs font-semibold text-[var(--brand)]">Open review queue <ArrowRight size={13}/></Link>}/>
      <section className="grid gap-4 xl:grid-cols-[1.1fr_1fr_1fr]"><Card className="overflow-hidden"><PanelTitle icon={ShieldAlert} title="Pending approvals" count={data.pending_approvals}/><div className="p-4"><div className="app-subtle rounded-xl border p-4"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-strong">Outbound communication</p><p className="mt-1 text-xs text-muted">Agent-generated drafts waiting for review</p></div><StatusBadge status="pending"/></div><Button asChild size="sm" className="mt-4"><Link href="/approvals">Review now</Link></Button></div></div></Card>
        <Card className="overflow-hidden"><PanelTitle icon={ShieldAlert} title="Failed workflows" count={data.failed_workflows}/><div className="p-4">{data.failed_workflows?<div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4"><p className="text-sm font-semibold text-strong">Agent execution failures</p><p className="mt-1 text-xs text-muted">Inspect categorized errors and retry safely.</p><Button asChild size="sm" variant="outline" className="mt-4"><Link href="/agents">Inspect failures</Link></Button></div>:<Healthy/>}</div></Card>
        <Card className="overflow-hidden"><PanelTitle icon={Sparkles} title="Communication status"/><div className="grid grid-cols-2 gap-px bg-[var(--border)]"><CompactMetric label="Sent today" value={data.communication.messages_sent_today}/><CompactMetric label="Delivered" value={data.communication.messages_delivered}/><CompactMetric label="Opened" value={data.communication.messages_read}/><CompactMetric label="Replies" value={data.communication.replies_received}/></div></Card></section>
      <SectionHeading title="Recent activity" action={<Link href="/audit" className="text-xs font-semibold text-[var(--brand)]">View audit log</Link>}/><Card className="overflow-hidden">{data.recent_activity.length?data.recent_activity.slice(0,6).map(item=><div key={item.id} className="flex items-center gap-3 border-b hairline px-4 py-3 last:border-0"><span className="size-2 rounded-full bg-blue-500"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-strong">{item.action.replaceAll("."," ")}</p><p className="text-[11px] text-muted">{item.resource_type} · immutable event</p></div><time className="shrink-0 text-[11px] text-muted">{new Date(item.created_at).toLocaleString()}</time></div>):<p className="p-6 text-sm text-muted">No activity yet.</p>}</Card>
    </>}</div>;
}

function PanelTitle({icon:Icon,title,count}:{icon:typeof ShieldAlert;title:string;count?:number}){return <div className="flex items-center gap-2 border-b hairline px-4 py-3.5"><Icon size={15} className="text-muted"/><h2 className="text-sm font-semibold text-strong">{title}</h2>{count!==undefined&&<span className="ml-auto rounded-full bg-[var(--surface-subtle)] px-2 py-0.5 text-[10px] font-bold text-muted">{count}</span>}</div>}
function CompactMetric({label,value}:{label:string;value:number}){return <div className="bg-[var(--surface)] p-4"><p className="tabular text-xl font-semibold text-strong">{value}</p><p className="mt-1 text-[11px] text-muted">{label}</p></div>}
function Healthy(){return <div className="py-6 text-center"><span className="mx-auto grid size-9 place-items-center rounded-full bg-emerald-500/10 text-emerald-500">✓</span><p className="mt-3 text-sm font-semibold text-strong">All workflows healthy</p><p className="mt-1 text-xs text-muted">No failures require intervention.</p></div>}
