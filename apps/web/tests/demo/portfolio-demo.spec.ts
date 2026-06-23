import { expect, test, type Page } from "@playwright/test";
import { createHmac } from "node:crypto";

async function chapter(page: Page, eyebrow: string, title: string, detail: string, hold = 7_000) {
  await page.evaluate(({ eyebrow, title, detail }) => {
    document.getElementById("orbitops-demo-chapter")?.remove();
    const overlay = document.createElement("div");
    overlay.id = "orbitops-demo-chapter";
    overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;background:radial-gradient(circle at 50% 30%,rgba(30,64,175,.42),transparent 42%),linear-gradient(145deg,#050816 0%,#0b1224 55%,#071827 100%);color:white;font-family:Inter,ui-sans-serif,system-ui,sans-serif;";
    overlay.innerHTML = `<div style="width:min(760px,82vw);padding:52px;border:1px solid rgba(148,163,184,.22);border-radius:28px;background:rgba(15,23,42,.78);box-shadow:0 32px 100px rgba(0,0,0,.48);backdrop-filter:blur(22px)"><div style="font-size:13px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#5eead4">${eyebrow}</div><h1 style="margin:18px 0 14px;font-size:48px;line-height:1.05;letter-spacing:-.04em">${title}</h1><p style="margin:0;max-width:650px;font-size:20px;line-height:1.55;color:#a8b4c7">${detail}</p><div style="margin-top:36px;display:flex;align-items:center;gap:12px;color:#64748b;font-size:13px"><span style="width:34px;height:2px;background:#2dd4bf"></span>OrbitOps product walkthrough</div></div>`;
    document.body.appendChild(overlay);
  }, { eyebrow, title, detail });
  await page.waitForTimeout(hold);
  await page.evaluate(() => document.getElementById("orbitops-demo-chapter")?.remove());
  await page.waitForTimeout(900);
}

test("record the OrbitOps end-to-end portfolio demo", async ({ page, request }) => {
  await page.goto("/login");
  await chapter(page, "Multi-agent business automation", "OrbitOps", "From qualified lead to governed AI execution, customer engagement, reporting, and operational intelligence.", 9_000);

  await chapter(page, "01 · Secure access", "Login and tenant controls", "JWT authentication, role-based permissions, and tenant isolation protect every workflow and data boundary.", 6_000);
  await page.getByLabel("Email").fill("admin@example.com");
  await page.waitForTimeout(1_200);
  await page.getByLabel("Password").fill("TestOnly-Password-123!");
  await page.waitForTimeout(1_200);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(8_000);

  await chapter(page, "02 · Lead operations", "Create a qualified lead", "Capture business context and intent signals before the autonomous workflow begins.");
  await page.getByRole("link", { name: "Leads" }).click();
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Add lead" }).click();
  await expect(page.getByRole("heading", { name: "Create lead" })).toBeVisible();
  await page.waitForTimeout(4_000);
  const company = "Northstar Cloud Systems";
  await page.getByLabel("Lead name").fill("Asha Raman");
  await page.getByLabel("Company").fill(company);
  await page.getByLabel("Industry").fill("B2B SaaS");
  await page.getByLabel("Website").fill("https://example.com");
  await page.getByLabel("Email").fill("asha@example.com");
  await page.getByLabel(/Intent score/).fill("20");
  await page.waitForTimeout(4_000);
  await page.getByRole("button", { name: "Save lead" }).click();
  await expect(page.getByText("Lead created successfully.")).toBeVisible();
  await page.waitForTimeout(7_000);

  const leadCard = page.getByTestId("lead-card").filter({ hasText: company });
  const leadHref = await leadCard.getByRole("link", { name: "Asha Raman", exact: true }).getAttribute("href");
  const leadId = leadHref!.split("/").pop()!;
  await chapter(page, "03 · Agent orchestration", "Run the workflow", "Sales, research, and email agents execute in sequence before the workflow pauses at a human approval gate.");
  await leadCard.getByRole("button", { name: /Run agents/ }).click();
  await expect(page.getByText(/Approval is waiting/)).toBeVisible();
  await page.waitForTimeout(8_000);

  await leadCard.getByRole("link", { name: "Asha Raman", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Agent workflow timeline" })).toBeVisible();
  await chapter(page, "04 · Agent execution", "A transparent LangGraph timeline", "Every node exposes status, timing, output context, retries, and the persisted workflow checkpoint.", 7_000);
  await page.waitForTimeout(13_000);

  await chapter(page, "05 · Human in the loop", "Review before external action", "A manager reviews research and the generated communication draft before approving delivery and report generation.");
  await page.getByRole("link", { name: /Approvals/ }).click();
  await expect(page.getByRole("heading", { name: "Approval center" })).toBeVisible();
  await page.waitForTimeout(10_000);
  page.once("dialog", dialog => dialog.accept());
  const approvalCard = page.getByRole("heading", { name: new RegExp(`Asha Raman.*${company}`) }).locator("..").locator("..").locator("..");
  await approvalCard.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approval recorded and report generated.")).toBeVisible();
  await page.waitForTimeout(8_000);

  await chapter(page, "06 · Executive reporting", "Generate and preview the report", "Approval resumes the graph, generates the business report, and stores downloadable report metadata.");
  await page.getByRole("link", { name: "Reports" }).click();
  const reportCard = page.getByTestId("report-card").filter({ hasText: company });
  await expect(reportCard).toBeVisible();
  await page.waitForTimeout(6_000);
  await reportCard.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Report preview")).toBeVisible();
  await page.waitForTimeout(13_000);

  await chapter(page, "07 · Governance", "Immutable audit trail", "Authentication, lead creation, agent steps, approval decisions, reports, communications, and failures remain tenant-scoped and auditable.");
  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("cell", { name: "lead.created", exact: true }).first()).toBeVisible();
  await page.waitForTimeout(15_000);

  await chapter(page, "08 · Communication delivery", "Track the customer lifecycle", "OrbitOps records approval, send, delivery, open, reply, classification, and the recommended next action.");
  await page.getByRole("link", { name: "Communications" }).click();
  const messageCard = page.locator(".app-surface").filter({ hasText: company }).first();
  await expect(messageCard).toBeVisible();
  await page.waitForTimeout(7_000);
  await messageCard.getByRole("button", { name: "Send" }).click();
  await expect(messageCard.getByText("sent", { exact: true })).toBeVisible();
  const messages = await page.evaluate(async id => {
    const response = await fetch(`/api/backend/communications?lead_id=${id}`);
    return response.json();
  }, leadId);
  const outbound = messages.find((item: { direction: string }) => item.direction === "outbound");
  for (const [status, replyText] of [["delivered", null], ["opened", null], ["replied", "Interested — please schedule a demo."]] as const) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const body = JSON.stringify({ event_id: `demo-${status}-${Date.now()}`, message_id: outbound.provider_message_id, status, timestamp: new Date().toISOString(), reply_text: replyText });
    const signature = createHmac("sha256", "test-only-email-webhook-secret-32").update(`${timestamp}.${body}`).digest("hex");
    const webhook = await request.post("http://127.0.0.1:8000/api/v1/webhooks/email", { data: body, headers: { "Content-Type": "application/json", "X-OrbitOps-Timestamp": timestamp, "X-OrbitOps-Signature": `sha256=${signature}` } });
    expect(webhook.ok(), `${status} webhook returned ${webhook.status()}: ${await webhook.text()}`).toBeTruthy();
    await page.waitForTimeout(1_500);
  }
  await messageCard.getByRole("link", { name: company, exact: true }).click();
  await expect(page.getByText("Email Delivered")).toBeVisible();
  await expect(page.getByText("Email Opened")).toBeVisible();
  await expect(page.getByText("Email Replied")).toBeVisible();
  await expect(page.getByText(/Meeting Requested/).first()).toBeVisible();
  await page.waitForTimeout(17_000);

  await chapter(page, "09 · AI operations", "Monitor the agent fleet", "Reliability, latency, token usage, cost, retries, and recent executions make the autonomous system measurable and operable.");
  await page.getByRole("link", { name: "Agent monitor" }).click();
  await expect(page.getByRole("heading", { name: "Agent monitoring" })).toBeVisible();
  await page.waitForTimeout(19_000);

  await chapter(page, "Production-minded AI automation", "OrbitOps", "One governed flow: Login → Lead → Agents → Approval → Report → Audit → Communication → Monitoring.", 11_000);
});
