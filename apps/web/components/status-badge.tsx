import { cn } from "@/lib/utils";

export function StatusBadge({ status }: { status:string }) {
  const normalized = status.toLowerCase();
  const color = normalized.includes("fail") || normalized.includes("reject") || normalized.includes("cancel")
    ? "border-red-400/20 bg-red-400/10 text-red-300"
    : normalized.includes("wait") || normalized.includes("pending") || normalized.includes("change")
      ? "border-amber-400/20 bg-amber-400/10 text-amber-300"
      : normalized.includes("complete") || normalized.includes("approve") || normalized.includes("generated") || normalized.includes("active")
        ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
        : "border-sky-400/20 bg-sky-400/10 text-sky-300";
  return <span className={cn("inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize", color)}>{status.replaceAll("_", " ")}</span>;
}
