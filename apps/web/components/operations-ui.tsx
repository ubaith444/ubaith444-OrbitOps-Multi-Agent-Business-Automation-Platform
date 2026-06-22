import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ChartPoint } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({label,value,detail,trend,icon:Icon,tone="blue"}:{label:string;value:React.ReactNode;detail?:string;trend?:number;icon:LucideIcon;tone?:"blue"|"violet"|"amber"|"emerald"|"rose"|"cyan"}){
  const colors={blue:"bg-blue-500/10 text-blue-500",violet:"bg-violet-500/10 text-violet-500",amber:"bg-amber-500/10 text-amber-500",emerald:"bg-emerald-500/10 text-emerald-500",rose:"bg-rose-500/10 text-rose-500",cyan:"bg-cyan-500/10 text-cyan-500"};
  const Trend=trend===undefined?Minus:trend>=0?ArrowUpRight:ArrowDownRight;
  return <Card className="p-4 sm:p-5"><div className="flex items-start justify-between"><span className={cn("grid size-9 place-items-center rounded-lg",colors[tone])}><Icon size={17}/></span>{trend!==undefined&&<span className={cn("flex items-center gap-0.5 text-[11px] font-semibold",trend>=0?"text-emerald-500":"text-rose-500")}><Trend size={12}/>{Math.abs(trend)}%</span>}</div><p className="tabular mt-4 text-[26px] font-semibold tracking-[-.03em] text-strong">{value}</p><p className="mt-0.5 text-xs font-medium text-muted">{label}</p>{detail&&<p className="mt-2 text-[10px] text-muted">{detail}</p>}</Card>
}

export function TrendChart({title,description,data,color="#3b82f6",suffix=""}:{title:string;description?:string;data:ChartPoint[];color?:string;suffix?:string}){
  const values=data.map(item=>item.value),max=Math.max(...values,1),min=Math.min(...values,0),range=Math.max(max-min,1);
  const points=data.map((item,index)=>`${data.length===1?50:index/(data.length-1)*100},${92-(item.value-min)/range*72}`).join(" ");
  const last=data.at(-1)?.value||0;
  return <Card className="overflow-hidden"><div className="flex items-start justify-between p-5 pb-2"><div><h2 className="text-sm font-semibold text-strong">{title}</h2>{description&&<p className="mt-1 text-xs text-muted">{description}</p>}</div><p className="tabular text-xl font-semibold text-strong">{last.toLocaleString()}{suffix}</p></div><div className="h-40 px-3 pb-3"><svg role="img" aria-label={`${title} trend`} viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full overflow-visible"><defs><linearGradient id={`g-${title.replaceAll(' ','-')}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".22"/><stop offset="1" stopColor={color} stopOpacity="0"/></linearGradient></defs><path d={`M ${points} L 100,100 L 0,100 Z`} fill={`url(#g-${title.replaceAll(' ','-')})`}/><polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round"/></svg></div><div className="flex justify-between border-t hairline px-5 py-3 text-[10px] text-muted">{data.slice(0,6).map(item=><span key={item.label}>{item.label}</span>)}</div></Card>
}

export function SectionHeading({title,action}:{title:string;action?:React.ReactNode}){return <div className="mb-3 mt-7 flex items-center justify-between"><h2 className="text-sm font-semibold text-strong">{title}</h2>{action}</div>}
