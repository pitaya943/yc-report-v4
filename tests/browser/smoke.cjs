// Sign in and out the way a person does, in a real browser.
// Settings come from the environment: BASE_URL, GROUP, NAME, PASSWORD, and
// optionally SCREENSHOT_DIR. Exits non-zero at the first step that does not hold.
const path = require("node:path");
const { chromium } = require("playwright");

const { BASE_URL, GROUP, NAME, PASSWORD, SCREENSHOT_DIR } = process.env;
const WAIT = { timeout: 15000 };

async function main() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(WAIT.timeout);
    let shot = 0;
    const step = async (name) => {
      console.log(`ok: ${name}`);
      if (SCREENSHOT_DIR) {
        shot += 1;
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${shot}-${name}.png`) });
      }
    };
    const expectText = async (selector, text) => {
      await page.locator(selector, { hasText: text }).first().waitFor(WAIT);
    };

    await page.goto(`${BASE_URL}/`);
    await page.waitForURL("**/sign-in", WAIT);
    await step("sign-in-page");

    await page.selectOption('select[name="group"]', GROUP);
    // The names arrive from the server once a group is chosen.
    await page.locator(`#name option[value="${NAME}"]`).waitFor({ state: "attached", ...WAIT });
    await page.selectOption("#name", NAME);
    await page.fill('input[name="password"]', PASSWORD);
    await step("group-and-name-chosen");

    await page.getByRole("button", { name: "登入" }).click();
    await page.waitForURL((url) => !url.pathname.startsWith("/sign-in"), WAIT);
    const landing = page.url();
    await expectText("#signed-in-as", NAME);
    await step("landing-page");

    await page.getByRole("button", { name: "登出" }).click();
    await page.waitForURL("**/sign-in?signed-out", WAIT);
    await expectText('[role="status"]', "您已登出");
    await step("signed-out");

    await page.goto(landing);
    await expectText('[role="alert"]', "請重新登入");
    await step("landing-page-asks-to-sign-in-again");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
