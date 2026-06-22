import { expect, test } from "@playwright/test";
import path from "node:path";

const output = path.resolve(process.cwd(), "../../docs/assets/screenshots");

test("capture GitHub portfolio assets", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => localStorage.setItem("orbitops-theme", "dark"));
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("TestOnly-Password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();

  const seed = await page.evaluate(async () => {
    const leads = [
      { name:"Maya Chen", company:"Northstar Cloud", industry:"B2B SaaS", email:"maya@example.com", phone:"+15555550101", attributes:{intent_score:20} },
      { name:"Arun Patel", company:"Lumina Logistics", industry:"Supply Chain", email:"arun@example.com", attributes:{intent_score:14} },
      { name:"Sofia Reyes", company:"Helio Health", industry:"Healthcare Technology", email:"sofia@example.com", attributes:{intent_score:9} },
    ];
    const created=[];
    for (const lead of leads) {
      const response=await fetch("/api/backend/leads",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(lead)});
      created.push(await response.json());
    }
    const runResponse=await fetch("/api/backend/workflows",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({lead_id:created[0].id})});
    const run=await runResponse.json();
    return {created,run};
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
  await expect(page.getByText("Total leads")).toBeVisible();
  await page.screenshot({ path:path.join(output,"dashboard.png") });

  await page.goto("/leads");
  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();
  await expect(page.getByTestId("lead-card").filter({ hasText:"Northstar Cloud" }).first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"leads.png") });

  await page.goto("/workflows");
  await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();
  await expect(page.getByRole("link", { name:"Northstar Cloud" }).first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"workflows.png") });

  await page.goto("/approvals");
  await expect(page.getByRole("heading", { name: "Approval center" })).toBeVisible();
  await expect(page.getByRole("heading", { name:"Maya Chen · Northstar Cloud" }).first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"approvals.png") });

  await page.evaluate(async (runId) => {
    const response=await fetch("/api/backend/approvals?status=pending");
    const approvals=await response.json();
    const approval=approvals.find((item:{run_id:string})=>item.run_id===runId);
    await fetch(`/api/backend/approvals/${approval.id}/decision`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"approve",note:"Portfolio demo approval"})});
  }, seed.run.id);

  await page.goto("/communications");
  await expect(page.getByRole("heading", { name:"Communications" })).toBeVisible();
  await expect(page.getByText("Northstar Cloud").first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"communications.png") });

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(page.getByRole("heading", { name:"Lead intelligence: Northstar Cloud" }).first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"reports.png") });

  await page.goto("/ai-ops");
  await expect(page.getByRole("heading", { name: "AI Operations & Reliability" })).toBeVisible();
  await expect(page.getByText("Agent reliability")).toBeVisible();
  await page.screenshot({ path:path.join(output,"ai-operations.png") });

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name:"Agent monitoring" })).toBeVisible();
  await expect(page.getByText("Agent health")).toBeVisible();
  await page.screenshot({ path:path.join(output,"agent-monitor.png") });

  await page.setViewportSize({ width:390, height:844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
  await expect(page.getByText("Total leads")).toBeVisible();
  await page.screenshot({ path:path.join(output,"mobile-dashboard.png") });
  await page.goto("/leads");
  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();
  await expect(page.getByTestId("lead-card").filter({ hasText:"Northstar Cloud" }).first()).toBeVisible();
  await page.screenshot({ path:path.join(output,"mobile-leads.png") });
  await page.getByRole("button", { name:"Open navigation" }).click();
  await expect(page.getByRole("navigation", { name:"Mobile navigation" })).toBeVisible();
  await page.screenshot({ path:path.join(output,"mobile-navigation.png") });
});
