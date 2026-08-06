const { chromium, webkit } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const source = path.join(root, "examples/knowledge/ocean-literacy-2024.pdf");
const accessCode = process.env.STUDIO_ACCESS_CODE;
const frontendBaseUrl = (process.env.FRONTEND_BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const backendBaseUrl = (process.env.BACKEND_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

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
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const chrome = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const studioContext = await chrome.newContext({ viewport: { width: 1440, height: 1100 } });
  const studio = await studioContext.newPage();
  studio.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`chromium:${message.text()}`);
  });
  await studio.goto(`${frontendBaseUrl}/access`);
  await studio.getByLabel("Access code").fill(accessCode);
  await studio.getByRole("button", { name: "Enter Studio" }).click();
  await studio.waitForURL("**/studio");
  await studio.getByRole("button", { name: "Create agent" }).click();
  await studio.getByRole("button", { name: "Create Ocean Explorer" }).click();
  await studio.waitForURL("**/studio/agents/**");
  await studio.getByRole("button", { name: /Knowledge/ }).click();
  await studio.locator('input[type="file"]').setInputFiles(source);
  await studio.getByRole("button", { name: "Use this source" }).click();
  await studio.getByRole("button", { name: /Test Open/ }).click({ timeout: 20_000 });
  await studio.getByText("Ready for grounded testing").waitFor({ timeout: 20_000 });
  await studio.getByRole("button", { name: /Submit Ready/ }).click();
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

  const desktopContext = await chrome.newContext({ viewport: { width: 1440, height: 1000 } });
  const desktop = await desktopContext.newPage();
  desktop.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`public-chromium:${message.text()}`);
  });
  await desktop.goto(`${frontendBaseUrl}/p/ocean-explorer`);
  await desktop.getByRole("heading", { name: "Ocean Explorer" }).waitFor();
  await ask(desktop, "How do ocean currents affect climate?");
  await desktop.getByText(/Ocean currents move heat around Earth/).waitFor({ timeout: 15_000 });
  await desktop.getByText(/ocean-literacy-2024.pdf · page/).first().click();
  await desktop.locator(".public-citations details[open]").waitFor();
  const desktopA11y = await new AxeBuilder({ page: desktop }).analyze();
  if (desktopA11y.violations.length) {
    throw new Error(`desktop accessibility violations: ${desktopA11y.violations.map((item) => `${item.id} (${item.nodes.map((node) => node.target.join(" ")).join(" | ")})`).join(", ")}`);
  }
  await desktop.screenshot({ path: "/tmp/agentsprout-m7-public-desktop.png", fullPage: true });

  const anonymous = await chrome.newContext();
  const denied = await anonymous.request.post(
    `${backendBaseUrl}/api/v1/studio/versions/not-public/withdraw`,
    { headers: { Origin: frontendBaseUrl, "Idempotency-Key": "public-cannot-mutate" } },
  );
  if (denied.status() !== 401) throw new Error(`anonymous Studio mutation returned ${denied.status()}`);
  await anonymous.close();

  const safari = await webkit.launch({ headless: true });
  const mobileContext = await safari.newContext({
    viewport: { width: 375, height: 812 },
    reducedMotion: "reduce",
  });
  const mobile = await mobileContext.newPage();
  mobile.on("console", (message) => {
    if (isUnexpectedConsoleError(message)) consoleErrors.push(`webkit:${message.text()}`);
  });
  await mobile.goto(`${frontendBaseUrl}/p/ocean-explorer`);
  await ask(mobile, "How does the ocean influence weather?");
  await mobile.getByText(/Ocean currents move heat around Earth/).waitFor({ timeout: 15_000 });
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (overflow) throw new Error("375px public page has horizontal overflow");
  const mobileA11y = await new AxeBuilder({ page: mobile }).analyze();
  if (mobileA11y.violations.length) {
    throw new Error(`mobile accessibility violations: ${mobileA11y.violations.map((item) => `${item.id} (${item.nodes.map((node) => node.target.join(" ")).join(" | ")})`).join(", ")}`);
  }
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
    axe_violations: 0,
    reduced_motion: true,
    direct_mutation_denied: true,
    rate_limit_state: true,
    console_errors: 0,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
