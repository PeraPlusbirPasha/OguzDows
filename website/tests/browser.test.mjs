import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { launchBrowser } from "../../mobile/preview/tests/browser-helper.mjs";

const require = createRequire(
  new URL("../../mobile/preview/package.json", import.meta.url),
);
const { AxeBuilder } = require("@axe-core/playwright");
const BASE = process.env.WEBSITE_BASE_URL || "http://127.0.0.1:4174/OguzDows/";
const CACHE = path.resolve(".cache/website");
const routes = [
  "",
  "indir/",
  "pc/",
  "raspberry-pi/",
  "telefon/",
  "oguzkopru/",
  "sss/",
];

test(
  "public website: real Chromium navigation, responsive UI, access and SEO",
  { timeout: 180000 },
  async (t) => {
    await fs.mkdir(CACHE, { recursive: true });
    const browser = await launchBrowser();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      locale: "tr-TR",
    });
    const requests = [];
    const errors = [];
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (req) => requests.push(req.url()));
    await context.route("**/*", (route) =>
      new URL(route.request().url()).origin === new URL(BASE).origin
        ? route.continue()
        : route.abort(),
    );
    try {
      for (const route of routes) {
        await t.test(
          `SSR metadata, local assets and axe on /${route}`,
          async () => {
            const response = await page.goto(BASE + route, {
              waitUntil: "networkidle",
            });
            assert.equal(response.status(), 200);
            assert.equal(await page.locator("h1").count(), 1);
            assert.equal(await page.locator("html").getAttribute("lang"), "tr");
            assert.equal(
              await page.locator('link[rel="canonical"]').getAttribute("href"),
              `https://peraplusbirpasha.github.io/OguzDows/${route}`,
            );
            const images = await page
              .locator("img")
              .evaluateAll((elements) =>
                elements.every((el) => el.complete && el.naturalWidth > 0),
              );
            assert.equal(images, true);
            const report = await new AxeBuilder({ page })
              .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
              .analyze();
            await fs.writeFile(
              path.join(
                CACHE,
                `axe-${route.replaceAll("/", "") || "home"}.json`,
              ),
              JSON.stringify(report.violations, null, 2),
            );
            assert.deepEqual(
              report.violations.map((v) => ({
                id: v.id,
                impact: v.impact,
                nodes: v.nodes.map((n) => n.target),
              })),
              [],
            );
          },
        );
      }
      await t.test(
        "320/390/768/1440px without horizontal overflow",
        async () => {
          for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({ width, height: 1000 });
            for (const route of routes) {
              await page.goto(BASE + route, { waitUntil: "load" });
              assert.equal(
                await page.evaluate(
                  () => document.documentElement.scrollWidth <= innerWidth,
                ),
                true,
                `${width} /${route}`,
              );
            }
            await page.goto(BASE, { waitUntil: "networkidle" });
            await page.screenshot({
              path: path.join(CACHE, `home-${width}.png`),
              fullPage: true,
            });
          }
        },
      );
      await t.test(
        "mobile menu: keyboard, real destinations and Escape restores focus",
        async () => {
          await page.setViewportSize({ width: 390, height: 844 });
          await page.goto(BASE);
          const menu = page.locator(".mobile-menu");
          const summary = menu.locator("summary");
          await summary.focus();
          await page.keyboard.press("Enter");
          assert.equal(await menu.getAttribute("open"), "");
          await page.keyboard.press("Escape");
          assert.equal(await menu.getAttribute("open"), null);
          assert.equal(
            await summary.evaluate((el) => document.activeElement === el),
            true,
          );
          await summary.click();
          await page
            .getByRole("navigation", { name: "Mobil menü", exact: true })
            .getByRole("link", { name: "İndir", exact: true })
            .click();
          assert.equal(page.url(), BASE + "indir/");
          assert.match(await page.locator("h1").innerText(), /Akıncı/);
        },
      );
      await t.test(
        "native FAQ and download hashes remain usable without JavaScript",
        async () => {
          const nojs = await browser.newContext({
            javaScriptEnabled: false,
            viewport: { width: 390, height: 844 },
          });
          await nojs.route("**/*", (route) =>
            new URL(route.request().url()).origin === new URL(BASE).origin
              ? route.continue()
              : route.abort(),
          );
          const tab = await nojs.newPage();
          await tab.goto(BASE + "sss/");
          const item = tab.locator(".faq-item").first();
          await item.locator("summary").click();
          assert.equal(await item.locator("p").isVisible(), true);
          await tab.goto(BASE + "indir/");
          await tab
            .getByText("SHA-256 özetini göster", { exact: true })
            .first()
            .click();
          assert.match(
            await tab.locator(".checksum code").first().innerText(),
            /^[0-9a-f]{64}$/,
          );
          assert.ok(
            (
              await tab
                .locator('a[href$="OguzDows-amd64.iso"]')
                .getAttribute("href")
            ).startsWith("https://github.com/"),
          );
          await nojs.close();
        },
      );
      await t.test(
        "copy hash/announcement succeeds or offers an accessible manual fallback",
        async () => {
          await page.goto(BASE + "indir/");
          await page
            .getByText("SHA-256 özetini göster", { exact: true })
            .first()
            .click();
          const card = page.locator(".download-card").first();
          await card
            .getByRole("button", { name: "Özeti kopyala", exact: true })
            .click();
          await page.waitForFunction(
            () =>
              document.querySelector(".download-card .copy-status")?.textContent
                .length > 0,
          );
          assert.match(
            await card.locator(".copy-status").innerText(),
            /kopyalandı|elle kopyalayabilirsin/,
          );
          await page
            .getByRole("button", {
              name: "Tanıtım metnini kopyala",
              exact: true,
            })
            .click();
          assert.match(
            await page.locator(".footer-grid .copy-status").innerText(),
            /kopyalandı|elle kopyalayabilirsin/,
          );
        },
      );
      await t.test(
        "no third-party automatic request, API call or client error",
        async () => {
          assert.equal(
            requests.every(
              (href) => new URL(href).origin === new URL(BASE).origin,
            ),
            true,
          );
          assert.equal(
            requests.some((href) => new URL(href).pathname.includes("/api/")),
            false,
          );
          assert.deepEqual(errors, []);
        },
      );
    } finally {
      await context.close();
      await browser.close();
    }
  },
);
