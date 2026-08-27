import { expect, test } from "@playwright/test";

const expectedProvider = process.env.COVAL_E2E_EXPECTED_PROVIDER ?? "mock";
const expectedExtractionVersion = process.env.COVAL_E2E_EXPECTED_EXTRACTION_VERSION ?? "mock-rules-v2";
const expectedNetworkGuard = process.env.COVAL_E2E_EXPECTED_NETWORK_GUARD === "true";


test("reviewed synthetic record persists, versions, and undoes", async ({ page, request }) => {
  const healthResponse = await request.get("http://127.0.0.1:18765/health");
  expect(healthResponse.ok()).toBeTruthy();
  const health = await healthResponse.json();
  expect(health.model_runtime.network_guard).toBe(expectedNetworkGuard);

  await page.goto("/");
  await expect(page.getByText(new RegExp(`API 已连接 · SQLite v8 · 推理 ${expectedProvider}`))).toBeVisible();
  await expect(page.getByText("仅限虚构或公开数据")).toBeVisible();
  await expect(page.getByText("等待确认保存")).toBeVisible();
  await expect(page.getByRole("button", { name: "智能整理" })).toBeDisabled();
  await page.getByLabel("仅使用虚构或公开数据").check();
  await page.getByRole("button", { name: "每日血压", exact: true }).click();

  await page.getByLabel("健康记录内容").fill(
    "E2E 手动输入：昨晚开始咳嗽，今天咽喉痛；没有胸痛，也没有喘不上气。"
  );
  await page.getByRole("textbox", { name: "记录来源", exact: true }).fill("E2E 任意手动记录");
  await page.getByRole("button", { name: "智能整理" }).click();
  await expect(page.getByLabel("医生摘要")).toBeVisible();
  const observationRow = page.getByRole("row").filter({ hasText: "检查" });
  await expect(observationRow).toContainText("未识别");
  await expect(observationRow).not.toContainText("146/88");
  await page.getByRole("button", { name: "核对", exact: true }).first().click();
  await expect(page.getByText("1/5 项已核对")).toBeVisible();
  await page.getByLabel("症状 结构化字段").fill("咳嗽、咽喉痛、低热");
  await expect(page.getByText("0/5 项已核对")).toBeVisible();
  await page.getByLabel("医生摘要").fill("E2E 家人已核对摘要：咳嗽和咽喉痛；仅用于复诊沟通。");
  await page.getByRole("button", { name: "确认保存到健康记忆" }).click();
  await expect(page.getByRole("button", { name: "已保存 v1" })).toBeVisible();

  await page.getByLabel("医生摘要").fill("E2E 第二版摘要：补充连续观察；不提供诊断或调药建议。");
  await page.getByRole("button", { name: "确认保存到健康记忆" }).click();
  await expect(page.getByRole("button", { name: "已保存 v2" })).toBeVisible();

  await page.getByRole("button", { name: "撤销到上一版" }).click();
  await expect(page.getByRole("button", { name: "已保存 v3" })).toBeVisible();
  await expect(page.getByLabel("医生摘要")).toHaveValue(/E2E 家人已核对摘要/);

  await page.reload();
  await expect(page.getByText(new RegExp(`API 已连接 · SQLite v8 · 推理 ${expectedProvider}`))).toBeVisible();
  const persistedCard = page.locator("article").filter({ hasText: /E2E 家人已核对摘要/ });
  await expect(persistedCard).toContainText(/· v3/);
  await expect(persistedCard).toContainText(/E2E 家人已核对摘要/);

  await page.getByLabel("仅使用虚构或公开数据").check();
  await page.getByRole("button", { name: "智能整理" }).click();
  await expect(page.getByLabel("医生摘要")).toBeVisible();

  const timelineResponse = await request.get("http://127.0.0.1:18765/timeline?member_id=mom");
  expect(timelineResponse.ok()).toBeTruthy();
  const timeline = await timelineResponse.json();
  expect(timeline).toHaveLength(1);
  expect(timeline[0].version_number).toBe(3);
  expect(timeline[0].source_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(timeline[0].extraction_version).toBe(expectedExtractionVersion);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText("仅限虚构或公开数据")).toBeVisible();
});

test("API failure is visible and disables persistence", async ({ page }) => {
  await page.route("http://127.0.0.1:18765/**", (route) => route.abort("connectionfailed"));
  await page.goto("/");

  await expect(page.getByText(/API 离线 · 写入已禁用/)).toBeVisible();
  await expect(page.getByText(/本地 API 不可用，写入已禁用/)).toBeVisible();
  await expect(page.getByRole("button", { name: "智能整理" })).toBeDisabled();
});
