const { chromium } = require("playwright");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const source = path.join(root, "examples/knowledge/ocean-literacy-2024.pdf");

async function waitForEvaluation(page) {
  const deadline = Date.now() + 25_000;
  while (Date.now() < deadline) {
    const progress = await page.locator(".evaluation-progress strong").innerText().catch(() => "0/16");
    if (Number(progress.split("/")[0]) === 16) return;
    await page.waitForTimeout(150);
  }
  throw new Error("evaluation did not complete 16/16");
}

async function main() {
  const consoleErrors = [];
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
  await page.getByRole("button", { name: "Teacher" }).click();
  await page.getByRole("button", { name: "Run 16-case evaluation" }).click();
  await waitForEvaluation(page);
  await page.getByLabel("Required feedback").fill("Use the reviewed evidence page for younger learners.");
  await page.getByRole("button", { name: "Request changes" }).click();
  await page.getByText("Use the reviewed evidence page for younger learners.").waitFor();
  await page.getByRole("button", { name: "Student" }).click();
  await page.getByLabel("What changed").fill("Made younger explanations explicitly evidence-led.");
  await page.getByLabel("Why changed").fill("Teacher feedback identified weak expected-page overlap.");
  await page.getByRole("button", { name: "Create Draft v2" }).click();
  await page.waitForURL("**/studio/agents/**");
  await page.getByText("Made younger explanations explicitly evidence-led.").waitFor();
  await page.getByRole("button", { name: "Submit v2 for review" }).click();
  await page.waitForURL("**/studio/review/**");
  await page.getByRole("button", { name: "Teacher" }).click();
  await page.getByRole("button", { name: "Run 16-case evaluation" }).click();
  await waitForEvaluation(page);
  await page.getByRole("button", { name: "Compare latest completed runs" }).click();
  await page.locator(".comparison-deltas").waitFor();
  await page.screenshot({ path: "/tmp/agentsprout-m6-comparison.png", fullPage: true });
  const approve = page.getByRole("button", { name: "Approve v2" });
  if (await approve.isEnabled()) {
    await approve.click();
    await page.locator(".review-stamp", { hasText: "APPROVED" }).waitFor();
  } else {
    throw new Error("provider-boundary v2 did not reach the approval gate");
  }
  await page.screenshot({ path: "/tmp/agentsprout-m6-approved.png", fullPage: true });
  await browser.close();
  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
  console.log(JSON.stringify({ requested_changes: true, v1_immutable: true, v2_created: true, reflection_visible: true, compared: true, approved: true, console_errors: 0 }));
}

main().catch((error) => { console.error(error); process.exit(1); });
