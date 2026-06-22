import { AlertTriangle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function LoadingState({ rows=3 }: { rows?:number }) {
  return <div role="status" aria-label="Loading" className="space-y-3">{Array.from({length:rows},(_,index)=><div key={index} className="h-20 animate-pulse rounded-2xl border border-white/5 bg-white/[.03]"/>)}</div>;
}
export function EmptyState({ title, detail }: { title:string; detail:string }) {
  return <Card className="p-10 text-center"><Inbox className="mx-auto mb-3 text-slate-600"/><h2 className="font-semibold text-white">{title}</h2><p className="mt-2 text-sm text-slate-500">{detail}</p></Card>;
}
export function ErrorState({ message, retry }: { message:string; retry:()=>void }) {
  return <Card role="alert" className="mb-5 border-red-400/15 p-5 text-red-300"><div className="flex items-center gap-2"><AlertTriangle size={18}/><p>{message}</p></div><Button variant="outline" className="mt-4" onClick={retry}>Try again</Button></Card>;
}
