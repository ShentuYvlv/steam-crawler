const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const rootDir = path.resolve(__dirname, "..");
const outputDir = path.join(__dirname, "screenshots", "raw");

const baseUrl = "http://127.0.0.1:5173";
const username = "docmanual";
const password = "Docmanual123";

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

async function waitForPage(page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1500);
}

async function shot(page, name, options = {}) {
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(outputDir, `${name}.png`),
    type: "png",
    fullPage: false,
    ...options,
  });
}

async function goto(page, route) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded" });
  await waitForPage(page);
}

async function clickControl(page, text) {
  const candidates = [
    page.getByRole("button", { name: text }).first(),
    page.getByRole("tab", { name: text }).first(),
    page.getByText(text, { exact: true }).first(),
  ];
  for (const locator of candidates) {
    if (await locator.count()) {
      await locator.waitFor({ state: "visible", timeout: 5000 });
      await locator.click();
      await page.waitForTimeout(1500);
      return;
    }
  }
  throw new Error(`Control not found: ${text}`);
}

async function main() {
  ensureDir(outputDir);
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 1.5,
    locale: "zh-CN",
  });
  const page = await context.newPage();

  await goto(page, "/");
  await shot(page, "01-login-page");

  await page.getByPlaceholder("用户名").fill(username);
  await page.getByPlaceholder("密码").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForTimeout(2500);

  await shot(page, "02-dashboard");

  await goto(page, "/games");
  await shot(page, "03-games-list");
  await page.evaluate(() => window.scrollTo(0, 700));
  await page.waitForTimeout(1000);
  await shot(page, "04-games-edit");

  await goto(page, "/reviews");
  await shot(page, "05-reviews-owned-pending");
  const firstReview = page.locator("tbody button").first();
  if ((await firstReview.count()) > 0) {
    await firstReview.click();
    await page.waitForTimeout(1800);
  }
  await shot(page, "06-reviews-detail");

  await clickControl(page, "已回复");
  await shot(page, "07-reviews-replied");

  await clickControl(page, "竞品");
  await shot(page, "08-reviews-competitor");

  await goto(page, "/reply-strategies");
  await shot(page, "09-reply-strategies");

  await goto(page, "/tasks");
  await shot(page, "10-tasks");

  await goto(page, "/task-queue");
  await shot(page, "11-task-queue");

  await goto(page, "/reply-records");
  await shot(page, "12-reply-records");

  await goto(page, "/users");
  await shot(page, "13-users");

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
