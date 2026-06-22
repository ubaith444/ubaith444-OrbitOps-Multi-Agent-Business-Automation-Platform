export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?:string; actions?:React.ReactNode }) {
  return (
    <header className="mb-6 flex items-end justify-between gap-5">
      <div><p className="eyebrow mb-1.5">{eyebrow}</p><h1 className="text-2xl font-semibold tracking-[-.025em] text-strong sm:text-[28px]">{title}</h1>{description&&<p className="mt-1.5 max-w-2xl text-sm text-muted">{description}</p>}</div>
      {actions&&<div className="hidden shrink-0 items-center gap-2 sm:flex">{actions}</div>}
    </header>
  );
}
