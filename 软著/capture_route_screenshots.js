const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const outputDir = path.join(__dirname, "screenshots", "raw");
const baseUrl = "http://127.0.0.1:5173";

const shots = [
  { name: "01-login-page", route: "/", login: false, scrollY: 0 },
  { name: "02-dashboard", route: "/", scrollY: 0 },
  { name: "03-games-list", route: "/games", scrollY: 0 },
  { name: "04-games-edit", route: "/games", scrollY: 760 },
  { name: "05-reviews-list", route: "/reviews", scrollY: 0 },
  { name: "06-reply-strategies", route: "/reply-strategies", scrollY: 0 },
  { name: "07-tasks", route: "/tasks", scrollY: 0 },
  { name: "08-task-queue", route: "/task-queue", scrollY: 0 },
  { name: "09-reply-records", route: "/reply-records", scrollY: 0 },
  { name: "10-users", route: "/users", scrollY: 0 },
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

async function waitForPage(page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1800);
}

async function login(page) {
  await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
  await waitForPage(page);
  await page.getByPlaceholder("用户名").fill("docmanual");
  await page.getByPlaceholder("密码").fill("Docmanual123");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForTimeout(2500);
}

async function main() {
  ensureDir(outputDir);
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 1.5,
    locale: "zh-CN",
  });
  const page = await context.newPage();

  for (const item of shots) {
    if (!item.login) {
      await page.goto(`${baseUrl}${item.route}`, { waitUntil: "domcontentloaded" });
      await waitForPage(page);
    } else {
      await page.goto(`${baseUrl}${item.route}`, { waitUntil: "domcontentloaded" });
      await waitForPage(page);
    }
    if (item.name === "01-login-page") {
      await page.screenshot({
        path: path.join(outputDir, `${item.name}.png`),
        type: "png",
      });
      await login(page);
      continue;
    }
    await page.goto(`${baseUrl}${item.route}`, { waitUntil: "domcontentloaded" });
    await waitForPage(page);
    if (item.scrollY > 0) {
      await page.evaluate((scrollY) => window.scrollTo(0, scrollY), item.scrollY);
      await page.waitForTimeout(1000);
    }
    await page.screenshot({
      path: path.join(outputDir, `${item.name}.png`),
      type: "png",
    });
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
