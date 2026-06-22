import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

export async function POST() {
  const jar = await cookies();
  const refreshToken = jar.get("orbitops_refresh")?.value;
  if (!refreshToken) return NextResponse.json({ detail: "Session expired" }, { status: 401 });
  const upstream = await fetch(`${API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!upstream.ok) {
    const response = NextResponse.json({ detail: "Session expired" }, { status: 401 });
    response.cookies.delete("orbitops_access");
    response.cookies.delete("orbitops_refresh");
    return response;
  }
  const tokens = await upstream.json();
  const response = NextResponse.json({ ok: true });
  const secure = process.env.NODE_ENV === "production";
  response.cookies.set("orbitops_access", tokens.access_token, {
    httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 30 * 60,
  });
  response.cookies.set("orbitops_refresh", tokens.refresh_token, {
    httpOnly: true, secure, sameSite: "strict", path: "/api/auth", maxAge: 14 * 24 * 60 * 60,
  });
  return response;
}
