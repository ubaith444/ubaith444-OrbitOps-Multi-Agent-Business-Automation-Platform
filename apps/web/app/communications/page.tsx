"use client";

import { Mail, MessageCircle, RotateCcw, Send } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Communication, Lead, User } from "@/lib/types";

export default function CommunicationsPage() {
  const [messages, setMessages] = useState<Communication[]>([]), [leads, setLeads] = useState<Lead[]>([]), [me, setMe] = useState<User | null>(null);
  const [channel, setChannel] = useState(""), [status, setStatus] = useState(""), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); setError(""); try { const query = new URLSearchParams(); if (channel) query.set("channel", channel); if (status) query.set("status", status); const [items, leadData, user] = await Promise.all([api<Communication[]>(`/communications?${query}`), api<Lead[]>("/leads?limit=200"), api<User>("/auth/me")]); setMessages(items); setLeads(leadData); setMe(user); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load communications"); } finally { setLoading(false); } }, [channel, status]);
  useEffect(() => { void load(); }, [load]);
  async function action(message: Communication, name: "send" | "retry") { await api(`/communications/${message.id}/${name}`, { method:"POST" }); await load(); }
  const canManage = me?.role === "admin" || me?.role === "manager";
  return <div className="mx-auto max-w-6xl"><PageHeader eyebrow="Delivery operations" title="Communications"/><div className="mb-5 grid gap-3 sm:grid-cols-2"><select aria-label="Filter communication channel" value={channel} onChange={event => setChannel(event.target.value)} className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2.5"><option value="">All channels</option><option value="email">Email</option><option value="whatsapp">WhatsApp</option></select><select aria-label="Filter communication status" value={status} onChange={event => setStatus(event.target.value)} className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2.5"><option value="">All statuses</option>{["draft","approved","queued","sent","delivered","opened","clicked","read","replied","bounced","failed","dead_letter"].map(value => <option key={value}>{value}</option>)}</select></div>{error && <ErrorState message={error} retry={load}/>} {loading ? <LoadingState/> : messages.length === 0 ? <EmptyState title="No communications" detail="Approved email and WhatsApp drafts will appear here."/> : <div className="space-y-3">{messages.map(message => { const lead = leads.find(item => item.id === message.lead_id); return <Card key={message.id} className="p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-start"><span className="grid size-10 place-items-center rounded-xl bg-cyan-400/10 text-cyan-300">{message.channel === "email" ? <Mail size={18}/> : <MessageCircle size={18}/>}</span><div className="flex-1"><div className="flex flex-wrap items-center gap-2"><Link href={`/leads/${message.lead_id}`} className="font-semibold text-white hover:text-teal-300">{lead?.company || "Lead communication"}</Link><StatusBadge status={message.status}/><StatusBadge status={message.direction}/></div><p className="mt-2 text-sm font-medium text-slate-300">{message.subject || `${message.channel} message`}</p><p className="mt-1 line-clamp-2 whitespace-pre-wrap text-sm text-slate-500">{message.body}</p><p className="mt-2 text-xs text-slate-700">{message.provider} · {new Date(message.created_at).toLocaleString()} · attempt {message.attempt_count}</p></div>{canManage && <div className="flex gap-2">{message.status === "approved" && <Button size="sm" onClick={() => action(message,"send")}><Send size={14}/>Send</Button>}{message.status === "failed" && <Button size="sm" onClick={() => action(message,"retry")}><RotateCcw size={14}/>Retry</Button>}</div>}</div></Card>; })}</div>}</div>;
}
