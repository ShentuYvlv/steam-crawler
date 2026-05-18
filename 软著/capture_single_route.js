const path = require("path");
const { chromium } = require("playwright");

async function login(page) {
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  await page.getByPlaceholder("用户名").fill("docmanual");
  await page.getByPlaceholder("密码").fill("Docmanual123");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForTimeout(2500);
}

async function main() {
  const [route, outputName, scrollRaw = "0"] = process.argv.slice(2);
  if (!route || !outputName) {
    throw new Error("usage: node capture_single_route.js <route> <outputName> [scrollY]");
  }

  const scrollY = Number(scrollRaw) || 0;
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 1.5,
    locale: "zh-CN",
  });
  const page = await context.newPage();

  await login(page);
  await page.goto(`http://127.0.0.1:5173${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2200);
  if (scrollY > 0) {
    await page.evaluate((value) => window.scrollTo(0, value), scrollY);
    await page.waitForTimeout(800);
  }
  await page.screenshot({
    path: path.join(__dirname, "screenshots", "raw", `${outputName}.png`),
    type: "png",
  });

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
