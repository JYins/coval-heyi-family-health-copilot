import { defineConfig } from "@playwright/test";
import { copyFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const appRoot = process.cwd();
const projectRoot = path.resolve(appRoot, "../..");
const e2eDatabase = path.join(tmpdir(), `coval-health-playwright-${process.pid}.sqlite`);
const e2eDistDir = `.next-e2e-${process.pid}`;
const e2eTsconfig = `tsconfig.e2e-${process.pid}.generated.json`;
const e2eTsconfigPath = path.join(appRoot, e2eTsconfig);
copyFileSync(path.join(appRoot, "tsconfig.json"), e2eTsconfigPath);
process.on("exit", () => rmSync(e2eTsconfigPath, { force: true }));
const e2eTimeoutMs = Number(process.env.COVAL_E2E_TIMEOUT_MS ?? "30000");
const python = process.env.COVAL_PYTHON ?? (
  process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : "python"
);

export default defineConfig({
  testDir: "./tests-e2e",
  outputDir: "../../output/playwright/test-results",
  reporter: [["line"]],
  timeout: e2eTimeoutMs,
  expect: {
    timeout: e2eTimeoutMs
  },
  use: {
    baseURL: "http://127.0.0.1:18766",
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn src.serve.coval_health_api:app --host 127.0.0.1 --port 18765 --log-level error`,
      cwd: projectRoot,
      env: {
        ...process.env,
        COVAL_HEALTH_DB_PATH: e2eDatabase,
        COVAL_ALLOWED_ORIGINS: "http://127.0.0.1:18766"
      },
      port: 18765,
      reuseExistingServer: false,
      timeout: 30_000
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 18766",
      cwd: appRoot,
      env: {
        ...process.env,
        COVAL_NEXT_DIST_DIR: e2eDistDir,
        COVAL_NEXT_TSCONFIG: e2eTsconfig,
        NEXT_PUBLIC_COVAL_API_BASE_URL: "http://127.0.0.1:18765"
      },
      port: 18766,
      reuseExistingServer: false,
      timeout: 60_000
    }
  ]
});
