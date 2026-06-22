import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("orbitops_access");
  response.cookies.delete("orbitops_refresh");
  return response;
}
