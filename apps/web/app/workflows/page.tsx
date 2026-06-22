"use client";

import { ArrowUpRight, Clock3, Filter, GitBranch, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Lead, Workflow } from "@/lib/types";

const stages=["Sales","Research","Email draft","Approval","Report"];
export default function WorkflowsPage(){
  const [runs,setRuns]=useState<Workflow[]>([]),[leads,setLeads]=useState<Lead[]>([]),[status,setStatus]=useState(""),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const load=useCallback(async()=>{setLoading(true);setError("");try{const [history,leadData]=await Promise.all([api<Workflow[]>("/workflows"),api<Lead[]>("/leads?limit=200")]);setRuns(history);setLeads(leadData)}catch(reason){setError(reason instanceof Error?reason.message:"Unable to load workflows")}finally{setLoading(false)}},[]);useEffect(()=>{void load()},[load]);
  async function retry(id:string){try{await api(`/workflows/${id}/retry`,{method:"POST"});await load()}catch(reason){setError(reason instanceof Error?reason.message:"Retry failed")}}
  const shown=status?runs.filter(run=>run.status===status):runs;
  return <div className="mx-auto max-w-[1480px]"><PageHeader eyebrow="Workflow orchestration" title="Workflows" description="Track every LangGraph run from qualification through report generation." actions={<Button variant="outline"><Filter size={15}/>Saved views</Button>}/>
    <div className="mb-4 flex gap-2 overflow-x-auto pb-1">{["","running","waiting_approval","completed","failed"].map(value=><Button key={value||"all"} size="sm" variant={status===value?"default":"outline"} onClick={()=>setStatus(value)}>{value?value.replaceAll("_"," "):"All runs"}</Button>)}</div>
    {error&&<ErrorState message={error} retry={load}/>} {loading?<LoadingState rows={5}/>:shown.length===0?<EmptyState title="No workflow runs" detail="Start an agent workflow from a lead to see its execution graph."/>:<div className="space-y-3">{shown.map(run=>{const lead=leads.find(item=>item.id===run.lead_id);const completed=(run.state_snapshot.events||[]).length;return <Card key={run.id} className="p-4 sm:p-5"><div className="flex flex-col gap-4 xl:flex-row xl:items-center"><div className="flex min-w-[240px] items-center gap-3"><span className="grid size-10 place-items-center rounded-lg bg-blue-500/10 text-blue-500"><GitBranch size={18}/></span><div className="min-w-0"><Link href={`/leads/${run.lead_id}`} className="truncate text-sm font-semibold text-strong hover:text-[var(--brand)]">{lead?.company||`Run ${run.id.slice(0,8)}`}</Link><p className="mt-0.5 text-[11px] text-muted">{lead?.name||run.id.slice(0,8)} · started {new Date(run.started_at||run.created_at).toLocaleString()}</p></div></div><div className="flex flex-1 items-center overflow-x-auto py-2 xl:px-5">{stages.map((stage,index)=><div key={stage} className="flex min-w-24 flex-1 items-center"><div className="flex flex-col items-center gap-1.5"><span className={`grid size-6 place-items-center rounded-full border text-[10px] font-bold ${index<completed||run.status==="completed"?"border-blue-500 bg-blue-500 text-white":index===completed&&run.status!=="failed"?"border-amber-500 bg-amber-500/10 text-amber-500":"hairline bg-[var(--surface-subtle)] text-muted"}`}>{index<completed||run.status==="completed"?"✓":index+1}</span><span className="whitespace-nowrap text-[10px] text-muted">{stage}</span></div>{index<stages.length-1&&<span className={`mb-4 h-px flex-1 ${index<completed?"bg-blue-500":"bg-[var(--border)]"}`}/>}</div>)}</div><div className="flex min-w-[180px] items-center justify-between gap-3 xl:justify-end"><StatusBadge status={run.status}/>{run.status==="failed"?<Button size="sm" onClick={()=>retry(run.id)}><RotateCcw size={13}/>Retry</Button>:<Button asChild size="icon" variant="ghost"><Link href={`/leads/${run.lead_id}`} aria-label="Open workflow"><ArrowUpRight size={16}/></Link></Button>}</div></div>{run.error&&<p className="mt-3 flex items-center gap-2 rounded-lg bg-rose-500/8 px-3 py-2 text-xs text-rose-500"><Clock3 size={13}/>{run.error}</p>}</Card>})}</div>}
  </div>
}
