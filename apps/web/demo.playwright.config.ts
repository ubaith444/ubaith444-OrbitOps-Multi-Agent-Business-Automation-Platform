import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/demo",
  outputDir: "../../work/demo-results",
  timeout: 360_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "chrome",
    viewport: { width: 1280, height: 720 },
    video: { mode: "on", size: { width: 1280, height: 720 } },
  },
  webServer: [
    {
      command: `${process.env.PYTHON_BIN ?? "python"} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: "../api",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: false,
      env: {
        APP_ENV: "test",
        DATABASE_URL: "sqlite+aiosqlite:///:memory:",
        APP_SECRET_KEY: "demo-secret-key-with-more-than-32-characters",
        BOOTSTRAP_ADMIN_PASSWORD: "TestOnly-Password-123!",
        EMAIL_WEBHOOK_SECRET: "test-only-email-webhook-secret-32",
        WHATSAPP_WEBHOOK_SECRET: "test-only-whatsapp-webhook-secret-32",
        PYTHONPATH: process.env.PYTHONPATH ?? "../../work/pydeps",
      },
    },
    {
      command: "node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3000",
      url: "http://127.0.0.1:3000/login",
      reuseExistingServer: false,
      env: { API_INTERNAL_URL: "http://127.0.0.1:8000/api/v1" },
    },
  ],
});
