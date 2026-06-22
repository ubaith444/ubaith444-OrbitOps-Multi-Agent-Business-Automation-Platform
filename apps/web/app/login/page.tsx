"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setLoading(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace:form.get('workspace'),email:form.get('email'),password:form.get('password')})});
      if(!response.ok){const body=await response.json();throw new Error(body.detail??'Login failed')}
      const target = new URLSearchParams(window.location.search).get('next');
      window.location.assign(target?.startsWith('/') ? target : '/');
    } catch (value) { setError(value instanceof Error ? value.message : 'Login failed'); setLoading(false); }
  }
  return <div className="grid min-h-screen place-items-center p-5"><div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-7 shadow-2xl"><p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-300">OrbitOps</p><h1 className="mt-2 text-3xl font-semibold text-white">Sign in</h1><p className="mt-2 text-sm text-slate-500">Access your tenant-scoped agent workspace.</p>
    <form onSubmit={submit} className="mt-7 space-y-4">
      <label className="block text-sm text-slate-300">Workspace<input name="workspace" defaultValue="default" required className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-3 outline-none focus:border-teal-400"/></label>
      <label className="block text-sm text-slate-300">Email<input name="email" type="email" autoComplete="email" defaultValue="admin@example.com" required className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-3 outline-none focus:border-teal-400"/></label>
      <label className="block text-sm text-slate-300">Password<input name="password" type="password" autoComplete="current-password" required minLength={8} className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-3 outline-none focus:border-teal-400"/></label>
      {error && <p role="alert" className="rounded-xl bg-red-400/10 p-3 text-sm text-red-300">{error}</p>}
      <Button className="w-full" disabled={loading}>{loading?'Signing in…':'Sign in'}</Button>
    </form></div></div>;
}
