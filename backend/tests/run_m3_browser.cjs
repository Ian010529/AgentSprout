const { chromium } = require("playwright");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "../..");
const noaaPdf = path.join(projectRoot, "examples/knowledge/ocean-literacy-2024.pdf");
const scannedPdf = "/tmp/agentsprout-scanned.pdf";

async function main() {
  const consoleErrors = [];
  const observed = new Set();
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("http://localhost:3000/access");
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Access code").fill("ocean-demo-code");
  await page.getByRole("button", { name: "Enter Studio" }).click();
  await page.waitForURL("**/studio");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("button", { name: "Create Ocean Explorer" }).click();
  await page.waitForURL("**/studio/agents/**");
  await page.waitForLoadState("networkidle");

  let fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(noaaPdf);
  await page.getByRole("button", { name: "Use this source" }).click();
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    const card = page.locator(".ingestion-card");
    if (await card.count()) {
      const text = await card.innerText();
      for (const state of ["Uploaded", "Extracting", "Chunking", "Embedding", "Ready"]) {
        if (text.includes(state)) observed.add(state.toUpperCase());
      }
    }
    if (
      (await page.getByText("Active evidence source").count()) &&
      (await page.getByText("Ready for grounded testing").count())
    ) break;
    await page.waitForTimeout(80);
  }
  if (!(await page.getByText("Ready for grounded testing").count())) {
    await page.screenshot({ path: "/tmp/agentsprout-m3-timeout.png", fullPage: true });
    const detail = await page.locator(".knowledge-workbench").innerText();
    throw new Error(`NOAA upload did not reach Ready: ${detail}`);
  }

  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.getByText("ocean-literacy-2024.pdf").waitFor();
  await page.getByText("Ready for grounded testing").waitFor();
  await page.screenshot({ path: "/tmp/agentsprout-m3-ready.png", fullPage: true });

  fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(scannedPdf);
  await page.getByRole("button", { name: "Replace source" }).click();
  await page.getByText("Source needs attention").waitFor({ timeout: 15_000 });
  await page.getByText("previous Ready source remains active", { exact: false }).waitFor();
  await page.getByText("ocean-literacy-2024.pdf").waitFor();
  await page.screenshot({ path: "/tmp/agentsprout-m3-failure.png", fullPage: true });

  await page.getByRole("button", { name: "Teacher" }).click();
  await page.getByText("Teacher view shows evidence status", { exact: false }).waitFor();
  if (!(await page.locator('input[type="file"]').isDisabled())) {
    throw new Error("Teacher file input is not disabled");
  }
  await browser.close();

  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
  console.log(JSON.stringify({ observed_stages: [...observed].sort(), console_errors: 0 }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
