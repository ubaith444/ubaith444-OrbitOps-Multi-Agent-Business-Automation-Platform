import { expect, test } from "@playwright/test";
import { createHmac } from "node:crypto";

test("login to lead, delivery reply, report download, and audit", async ({ page, request }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("TestOnly-Password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("link", { name: "Leads" }).click();
  await page.waitForLoadState("networkidle");
  const addLead = page.getByRole("button", { name: "Add lead" });
  await addLead.click();
  await expect(page.getByRole("heading", { name: "Create lead" })).toBeVisible();
  const company = `E2E Northstar ${Date.now()}`;
  await page.getByLabel("Lead name").fill("Asha Raman");
  await page.getByLabel("Company").fill(company);
  await page.getByLabel("Industry").fill("SaaS");
  await page.getByLabel("Website").fill("https://example.com");
  await page.getByLabel("Email").fill("asha@example.com");
  await page.getByLabel("Intent score (0–20)").fill("20");
  await page.getByRole("button", { name: "Save lead" }).click();
  await expect(page.getByText("Lead created successfully.")).toBeVisible();
  const leadCard = page.getByTestId("lead-card").filter({ hasText: company });
  const leadHref = await leadCard.getByRole("link", { name: "Asha Raman", exact: true }).getAttribute("href");
  const leadId = leadHref!.split("/").pop()!;
  await leadCard.getByRole("button", { name: /Run agents/ }).click();
  await expect(page.getByText(/Approval is waiting/)).toBeVisible();

  await leadCard.getByRole("link", { name: "Asha Raman", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Agent workflow timeline" })).toBeVisible();
  await expect(page.getByText("Research Agent").first()).toBeVisible();

  await page.getByRole("link", { name: /Approvals/ }).click();
  page.once("dialog", (dialog) => dialog.accept());
  const approvalCard = page
    .getByRole("heading", { name: new RegExp(`Asha Raman.*${company}`) })
    .locator("..")
    .locator("..")
    .locator("..");
  await approvalCard.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approval recorded and report generated.")).toBeVisible();

  await page.getByRole("link", { name: "Communications" }).click();
  const messageCard = page.locator(".app-surface").filter({ hasText: company }).first();
  await messageCard.getByRole("button", { name: "Send" }).click();
  const messages = await page.evaluate(async (id) => {
    const response = await fetch(`/api/backend/communications?lead_id=${id}`);
    return response.json();
  }, leadId);
  const outbound = messages.find((item: { direction:string }) => item.direction === "outbound");
  for (const [status, replyText] of [["delivered", null], ["opened", null], ["replied", "Interested — please schedule a demo."]] as const) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const body = JSON.stringify({ event_id:`e2e-${status}-${Date.now()}`, message_id:outbound.provider_message_id, status, timestamp:new Date().toISOString(), reply_text:replyText });
    const signature = createHmac("sha256", "test-only-email-webhook-secret-32").update(`${timestamp}.${body}`).digest("hex");
    const webhook = await request.post("http://127.0.0.1:8000/api/v1/webhooks/email", { data:body, headers:{"Content-Type":"application/json","X-OrbitOps-Timestamp":timestamp,"X-OrbitOps-Signature":`sha256=${signature}`} });
    expect(webhook.ok()).toBeTruthy();
  }
  await messageCard.getByRole("link", { name: company, exact: true }).click();
  await expect(page.getByRole("heading", { name: "Asha Raman" })).toBeVisible();
  await expect(page.getByText("Email Delivered")).toBeVisible();
  await expect(page.getByText("Email Opened")).toBeVisible();
  await expect(page.getByText("Email Replied")).toBeVisible();
  await expect(page.getByText(/Meeting Requested/).first()).toBeVisible();

  await page.getByRole("link", { name: "Reports" }).click();
  const reportCard = page.getByTestId("report-card").filter({ hasText: company });
  await reportCard.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Report preview")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await reportCard.getByRole("link", { name: "Download PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);

  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("cell", { name: "lead.created", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "approval.approved", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "report.generated", exact: true }).first()).toBeVisible();
});

test("mobile navigation exposes the P1 workspace", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("TestOnly-Password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agent monitor" })).toBeVisible();
  await expect(page.getByRole("link", { name: "AI Operations" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Users" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Workflows" })).toBeVisible();
  await page.getByRole("navigation", { name: "Mobile navigation" }).locator("..").getByRole("button", { name: "Close navigation", exact:true }).click();
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeHidden();
  const activeTheme = await page.locator("html").getAttribute("data-theme");
  await page.getByRole("button", { name: /^Switch to (light|dark) mode$/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", activeTheme === "dark" ? "light" : "dark");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Global search" })).toBeVisible();
  await page.getByLabel("Search workspace").press("Escape");
});

test("AI operations supports feedback, prompt versions, and playground runs", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("TestOnly-Password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: "AI Operations" }).click();
  await expect(page.getByRole("heading", { name: "AI Operations & Reliability" })).toBeVisible();
  await expect(page.getByText("Agent reliability")).toBeVisible();

  await page.getByRole("button", { name: "executions" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: /Good output/ }).first().click();
  await expect(page.getByText("Feedback recorded for agent quality metrics.")).toBeVisible();

  await page.getByRole("button", { name: "prompts" }).click();
  await page.getByLabel("Prompt agent").selectOption("email");
  await page.getByLabel("Prompt version name").fill(`E2E Prompt ${Date.now()}`);
  await page.getByLabel("Prompt instructions").fill("Draft a short evidence-based email and require human approval before delivery.");
  await page.getByRole("button", { name: "Create and activate" }).click();
  await expect(page.getByText("New prompt version created and activated.")).toBeVisible();

  await page.getByRole("button", { name: "playground" }).click();
  await page.getByLabel("Playground agent").selectOption("email");
  await page.getByLabel("Playground providers").selectOption("mock");
  await page.getByLabel("Playground prompt").fill("Write a concise follow-up for a qualified SaaS lead.");
  await page.getByRole("button", { name: "Run comparison" }).click();
  await expect(page.getByText("Playground comparison completed without changing production workflows.")).toBeVisible();
  await expect(page.getByText("local-deterministic")).toBeVisible();
});
