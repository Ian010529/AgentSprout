const { chromium, webkit } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;

const accessCode = process.env.STUDIO_ACCESS_CODE;
const frontendBaseUrl = (process.env.FRONTEND_BASE_URL || "http://localhost:3000").replace(/\/$/, "");

if (!accessCode) throw new Error("STUDIO_ACCESS_CODE is required for browser acceptance");

async function assertInFirstViewport(locator, label, viewportHeight = 1000) {
  await locator.waitFor();
  const box = await locator.boundingBox();
  if (!box || box.y >= viewportHeight || box.y + Math.min(box.height, 80) > viewportHeight) {
    throw new Error(`${label} is not available in the first viewport`);
  }
}

async function assertNoAxeViolations(page, label) {
  const result = await new AxeBuilder({ page }).analyze();
  if (result.violations.length) {
    throw new Error(`${label} accessibility violations: ${result.violations.map((item) => item.id).join(", ")}`);
  }
}

async function assertPublicTaskOrder(page, label) {
  const order = await page.evaluate(() => {
    const chat = document.querySelector(".public-chat");
    const about = document.querySelector(".public-about");
    const composer = document.querySelector(".public-composer");
    if (!chat || !about || !composer) return null;
    return {
      chatBeforeAbout: Boolean(chat.compareDocumentPosition(about) & Node.DOCUMENT_POSITION_FOLLOWING),
      composerInsideChat: chat.contains(composer),
      overflow: document.documentElement.scrollWidth > window.innerWidth,
    };
  });
  if (!order?.chatBeforeAbout || !order.composerInsideChat || order.overflow) {
    throw new Error(`${label} is not chat-first or introduces horizontal overflow`);
  }
}

async function main() {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const chrome = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const studioContext = await chrome.newContext({ viewport: { width: 1440, height: 1000 } });
  const studio = await studioContext.newPage();
  const consoleErrors = [];
  studio.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await studio.goto(`${frontendBaseUrl}/access`);
  await assertInFirstViewport(studio.getByRole("button", { name: "Enter Studio" }), "Access form");
  await studio.screenshot({ path: "/tmp/agentsprout-m9-access.png", fullPage: true });
  await studio.getByLabel("Access code").fill(accessCode);
  await studio.getByRole("button", { name: "Enter Studio" }).click();
  await studio.waitForURL("**/studio");
  await assertInFirstViewport(studio.getByRole("heading", { name: /Your agents|All agents/ }), "Workshop Agent list");
  await assertInFirstViewport(studio.getByRole("button", { name: "Create agent" }), "Workshop create action");
  await studio.screenshot({ path: "/tmp/agentsprout-m9-workshop.png", fullPage: true });

  const continueDraft = studio.getByRole("link", { name: "Continue Draft →" }).first();
  if (await continueDraft.count()) {
    await continueDraft.click();
    await studio.waitForURL("**/studio/agents/**");
    await assertInFirstViewport(studio.getByRole("button", { name: /Define/ }), "Workspace stage navigation");
    await assertInFirstViewport(studio.getByLabel("Project name"), "Workspace selected stage");
    await studio.screenshot({ path: "/tmp/agentsprout-m9-workspace.png", fullPage: true });
  }

  await studio.goto(`${frontendBaseUrl}/studio/reviews`);
  await assertInFirstViewport(studio.getByRole("heading", { name: "Ready for a decision" }), "Review queue");
  await studio.screenshot({ path: "/tmp/agentsprout-m9-reviews.png", fullPage: true });

  await studio.goto(`${frontendBaseUrl}/studio/published`);
  await assertInFirstViewport(studio.getByRole("heading", { name: "Published agents" }), "Published releases");
  await studio.screenshot({ path: "/tmp/agentsprout-m9-published.png", fullPage: true });
  const manageRelease = studio.getByRole("link", { name: "Manage release →" }).first();
  if (await manageRelease.count()) {
    await manageRelease.click();
    await studio.waitForURL("**/studio/review/**");
    const teacherRole = studio.getByRole("button", { name: "Teacher" });
    if ((await teacherRole.getAttribute("aria-pressed")) !== "true") {
      await teacherRole.click();
      await teacherRole.waitFor({ state: "visible" });
      await studio.waitForFunction(() => document.querySelector('button[aria-pressed="true"]')?.textContent?.trim() === "Teacher");
    }
    await assertInFirstViewport(studio.locator(".evaluation-hero"), "Teacher Review context and action");
    const evidence = studio.locator(".evaluation-progress");
    const runAction = studio.getByRole("button", { name: "Run 16-case evaluation" });
    if (await evidence.count()) await assertInFirstViewport(evidence, "Teacher Review evidence");
    else if (await runAction.count()) await assertInFirstViewport(runAction, "Teacher evaluation action");
    await studio.screenshot({ path: "/tmp/agentsprout-m9-teacher-review.png", fullPage: true });
  }

  const desktopContext = await chrome.newContext({ viewport: { width: 1440, height: 1000 } });
  const desktop = await desktopContext.newPage();
  await desktop.goto(`${frontendBaseUrl}/p/ocean-explorer`);
  await desktop.getByRole("heading", { name: "Ocean Explorer" }).waitFor();
  await assertInFirstViewport(desktop.getByLabel("Your question"), "Public composer");
  await assertPublicTaskOrder(desktop, "Desktop public Agent");
  await assertNoAxeViolations(desktop, "Desktop public Agent");
  await desktop.screenshot({ path: "/tmp/agentsprout-m9-public-desktop.png", fullPage: true });
  await chrome.close();

  const safari = await webkit.launch({ headless: true });
  const mobileContext = await safari.newContext({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
  const mobile = await mobileContext.newPage();
  await mobile.goto(`${frontendBaseUrl}/p/ocean-explorer`);
  await mobile.getByRole("heading", { name: "Ocean Explorer" }).waitFor();
  await assertPublicTaskOrder(mobile, "Mobile public Agent");
  await assertNoAxeViolations(mobile, "Mobile public Agent");
  await mobile.screenshot({ path: "/tmp/agentsprout-m9-public-mobile.png", fullPage: true });
  await safari.close();

  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
  console.log(JSON.stringify({
    first_viewport_tasks: true,
    desktop_chat_first: true,
    webkit_375_chat_first: true,
    horizontal_overflow: false,
    axe_violations: 0,
    console_errors: 0,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
