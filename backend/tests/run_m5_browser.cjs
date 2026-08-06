const { chromium } = require("playwright");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const source = path.join(root, "examples/knowledge/ocean-literacy-2024.pdf");

async function main() {
  const consoleErrors = [];
  const observed = new Set();
  const browser = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.goto("http://localhost:3000/access");
  await page.getByLabel("Access code").fill("ocean-demo-code");
  await page.getByRole("button", { name: "Enter Studio" }).click();
  await page.waitForURL("**/studio");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("button", { name: "Create Ocean Explorer" }).click();
  await page.waitForURL("**/studio/agents/**");
  await page.locator('input[type="file"]').setInputFiles(source);
  await page.getByRole("button", { name: "Use this source" }).click();
  await page.getByText("Ready for grounded testing").waitFor({ timeout: 20_000 });
  await page.getByRole("button", { name: "Submit v1 for review" }).click();
  await page.waitForURL("**/studio/review/**");
  await page.getByText("This version is locked.").waitFor();
  await page.getByRole("button", { name: "Teacher" }).click();
  await page.getByRole("button", { name: "Run 16-case evaluation" }).click();
  const deadline = Date.now() + 25_000;
  let refreshed = false;
  let completed = 0;
  while (Date.now() < deadline) {
    const progress = await page.locator(".evaluation-progress strong").innerText().catch(() => "0/16");
    completed = Number(progress.split("/")[0]);
    observed.add(completed);
    if (!refreshed && completed > 0 && completed < 16) {
      await page.reload();
      await page.waitForLoadState("networkidle");
      refreshed = true;
    }
    if (completed === 16) break;
    await page.waitForTimeout(150);
  }
  if (completed !== 16) {
    await page.screenshot({ path: "/tmp/agentsprout-m5-timeout.png", fullPage: true });
    throw new Error(`evaluation stopped at ${completed}/16`);
  }
  await page.locator(".case-table button").first().click();
  await page.getByRole("complementary", { name: "Evaluation case evidence" }).waitFor();
  const body = await page.locator("body").innerText();
  if (body.includes("eval-") && body.includes("@example.test")) throw new Error("PII canary reached the UI");
  await page.screenshot({ path: "/tmp/agentsprout-m5-evaluation.png", fullPage: true });
  await browser.close();
  if (!refreshed) throw new Error("evaluation completed before refresh restoration was exercised");
  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
  console.log(JSON.stringify({ completed: 16, observed_progress: [...observed].sort((a,b) => a-b), refresh_restored: refreshed, case_detail_opened: true, pii_exposed: false, console_errors: 0 }));
}

main().catch((error) => { console.error(error); process.exit(1); });
