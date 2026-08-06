const { chromium, webkit } = require("playwright");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const source = path.join(root, "examples/knowledge/ocean-literacy-2024.pdf");
const accessCode = process.env.STUDIO_ACCESS_CODE;

if (!accessCode) throw new Error("STUDIO_ACCESS_CODE is required for browser acceptance");

function isUnexpectedConsoleError(message) {
  return message.type() === "error" && !message.text().includes("status of 429");
}

async function waitForEvaluation(page) {
  const deadline = Date.now() + 25_000;
  while (Date.now() < deadline) {
    const progress = await page.locator(".evaluation-progress strong").innerText().catch(() => "0/16");
    if (Number(progress.split("/")[0]) === 16) return;
    await page.waitForTimeout(150);
  }
  throw new Error("evaluation did not complete 16/16");
}

async function ask(page, message) {
  await page.getByLabel("Your ocean question").fill(message);
  await page.getByRole("button", { name: "Ask Agent" }).click();
}

async function main() {
  const consoleErrors = [];
  const chrome = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  const studio = await chrome.newPage({ viewport: { width: 1440, height: 1100 } });
  studio.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`chromium:${message.text()}`);
  });
  await studio.goto("http://localhost:3000/access");
  await studio.getByLabel("Access code").fill(accessCode);
  await studio.getByRole("button", { name: "Enter Studio" }).click();
  await studio.waitForURL("**/studio");
  await studio.getByRole("button", { name: "Create agent" }).click();
  await studio.getByRole("button", { name: "Create Ocean Explorer" }).click();
  await studio.waitForURL("**/studio/agents/**");
  await studio.locator('input[type="file"]').setInputFiles(source);
  await studio.getByRole("button", { name: "Use this source" }).click();
  await studio.getByText("Ready for grounded testing").waitFor({ timeout: 20_000 });
  await studio.getByRole("button", { name: "Submit v1 for review" }).click();
  await studio.waitForURL("**/studio/review/**");
  await studio.getByRole("button", { name: "Teacher" }).click();
  await studio.getByRole("button", { name: "Run 16-case evaluation" }).click();
  await waitForEvaluation(studio);
  const approve = studio.getByRole("button", { name: "Approve v1" });
  if (!(await approve.isEnabled())) throw new Error("browser evaluation did not reach approval");
  await approve.click();
  await studio.getByRole("heading", { name: "Publish a stable public address." }).waitFor();
  await studio.getByLabel("Public slug").fill("ocean-explorer");
  await studio.getByLabel("I confirm this Approved version should be public.").check();
  await studio.getByRole("button", { name: "Publish v1" }).click();
  const publicLink = studio.getByRole("link", { name: /Open \/p\/ocean-explorer/ });
  await publicLink.waitFor();

  const desktop = await chrome.newPage({ viewport: { width: 1440, height: 1000 } });
  desktop.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`public-chromium:${message.text()}`);
  });
  await desktop.goto("http://localhost:3000/p/ocean-explorer");
  await desktop.getByRole("heading", { name: "Ocean Explorer" }).waitFor();
  await ask(desktop, "How do ocean currents affect climate?");
  await desktop.getByText(/Ocean currents move heat around Earth/).waitFor({ timeout: 15_000 });
  await desktop.getByText(/ocean-literacy-2024.pdf · page/).first().click();
  await desktop.locator(".public-citations details[open]").waitFor();
  await desktop.screenshot({ path: "/tmp/agentsprout-m7-public-desktop.png", fullPage: true });

  const anonymous = await chrome.newContext();
  const denied = await anonymous.request.post(
    "http://localhost:8000/api/v1/studio/versions/not-public/withdraw",
    { headers: { Origin: "http://localhost:3000", "Idempotency-Key": "public-cannot-mutate" } },
  );
  if (denied.status() !== 401) throw new Error(`anonymous Studio mutation returned ${denied.status()}`);
  await anonymous.close();

  const safari = await webkit.launch({ headless: true });
  const mobile = await safari.newPage({ viewport: { width: 375, height: 812 } });
  mobile.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`webkit:${message.text()}`);
  });
  await mobile.goto("http://localhost:3000/p/ocean-explorer");
  await ask(mobile, "How does the ocean influence weather?");
  await mobile.getByText(/Ocean currents move heat around Earth/).waitFor({ timeout: 15_000 });
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (overflow) throw new Error("375px public page has horizontal overflow");
  await mobile.screenshot({ path: "/tmp/agentsprout-m7-public-mobile.png", fullPage: true });
  await safari.close();

  for (const prompt of [
    "My email is limit-one@example.test",
    "My phone is +1 202 555 0171",
    "I live at 742 Evergreen Street",
  ]) {
    await ask(desktop, prompt);
    await desktop.getByText(/Keep personal contact details private/).last().waitFor();
  }
  await ask(desktop, "What is ocean literacy?");
  await desktop.getByRole("alert").getByText("Demo limit reached").waitFor();
  await desktop.screenshot({ path: "/tmp/agentsprout-m7-public-limit.png", fullPage: true });

  await chrome.close();
  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
  console.log(JSON.stringify({
    published: true,
    chromium_citation: true,
    webkit_375: true,
    direct_mutation_denied: true,
    rate_limit_state: true,
    console_errors: 0,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
