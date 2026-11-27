import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { launchBrowser, cache } from "./browser-helper.mjs";

const BASE = process.env.MOBILE_BASE_URL || "http://127.0.0.1:5173";
const KEY = "oguzdows.mobile.preview.v1";

test(
  "real Chromium mobile and desktop flows (not a ROM/device/model test)",
  { timeout: 180000 },
  async (t) => {
    const browser = await launchBrowser();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      locale: "tr-TR",
      acceptDownloads: true,
    });
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    const errors = [];
    const requests = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => requests.push(request.url()));
    await page.route("**/*", (route) =>
      new URL(route.request().url()).origin === new URL(BASE).origin
        ? route.continue()
        : route.abort(),
    );
    const home = () =>
      page
        .getByRole("button", { name: "Ana ekran hareket çubuğu", exact: true })
        .click();
    async function fresh(width = 390, height = 844) {
      await page.setViewportSize({ width, height });
      await page.goto(BASE);
      await page.evaluate((key) => {
        localStorage.removeItem(key);
        history.replaceState({}, "", "#/home");
      }, KEY);
      await page.reload({ waitUntil: "networkidle" });
      await page.evaluate(() => document.fonts.ready);
    }
    try {
      await t.test(
        "desktop layout and no third-party/API request on startup",
        async () => {
          await fresh(1440, 1000);
          assert.equal(
            await page.title(),
            "OğuzDows Mobile · Cebinde, senden bir dünya.",
          );
          assert.equal(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
            true,
          );
          assert.equal(await page.locator(".story-column").isVisible(), true);
          assert.equal(
            requests.some((url) => new URL(url).pathname.startsWith("/api/")),
            false,
          );
          assert.equal(
            requests.every(
              (url) => new URL(url).origin === new URL(BASE).origin,
            ),
            true,
          );
          await page.screenshot({
            path: path.join(cache, "desktop-final.png"),
            fullPage: true,
          });
        },
      );
      await t.test(
        "390px layout fills viewport and home fits without horizontal overflow",
        async () => {
          await fresh();
          assert.equal(await page.locator(".story-column").isVisible(), false);
          const dimensions = await page.evaluate(() => ({
            width: document.documentElement.scrollWidth,
            viewport: innerWidth,
            body: document.documentElement.scrollHeight,
            viewportH: innerHeight,
            home: document.querySelector(".home-content").clientHeight,
            scroll: document.querySelector(".home-content").scrollHeight,
          }));
          assert.equal(dimensions.width, dimensions.viewport);
          assert.equal(dimensions.body, dimensions.viewportH);
          assert.ok(dimensions.scroll <= dimensions.home + 1);
          assert.equal(
            await page.getByText("ÖNİZLEME", { exact: true }).isVisible(),
            true,
          );
          await page.screenshot({ path: path.join(cache, "phone-final.png") });
        },
      );
      await t.test(
        "Nazar power menu traps focus, Escape restores focus, and preview lock reopens",
        async () => {
          const power = page.getByRole("button", {
            name: "Nazar boncuğu güç menüsü",
          });
          await power.click();
          assert.equal(await page.getByRole("dialog").isVisible(), true);
          await page.keyboard.press("Shift+Tab");
          assert.match(
            await page.evaluate(() => document.activeElement.textContent),
            /Önizleme ekranını kapat/,
          );
          await page.keyboard.press("Tab");
          assert.equal(
            await page.evaluate(() =>
              document.activeElement.getAttribute("aria-label"),
            ),
            "Pencereyi kapat",
          );
          await page.keyboard.press("Escape");
          assert.equal(await page.getByRole("dialog").count(), 0);
          assert.equal(
            await page.evaluate(() =>
              document.activeElement.getAttribute("aria-label"),
            ),
            "Nazar boncuğu güç menüsü",
          );
          await power.click();
          await page
            .getByRole("button", { name: /Kilit ekranını dene/ })
            .click();
          assert.equal(
            await page.getByText(/güvenlik kilidi değildir/).isVisible(),
            true,
          );
          await page
            .getByRole("button", { name: "Önizlemeyi aç", exact: true })
            .click();
          assert.equal(await page.locator(".lock-screen").count(), 0);
        },
      );
      await t.test(
        "quick settings are explicitly illustrative while theme really synchronizes and persists",
        async () => {
          await page
            .getByRole("button", { name: "Denetim merkezini aç" })
            .click();
          assert.equal(
            await page.getByText(/gerçek Wi-Fi, Bluetooth/).isVisible(),
            true,
          );
          await page
            .getByRole("switch", { name: "Koyu görünüm", exact: true })
            .click();
          assert.equal(await page.locator(".lab.theme-dark").count(), 1);
          await page.getByRole("button", { name: "Pencereyi kapat" }).click();
          await page
            .getByRole("button", { name: "Ayarlar", exact: true })
            .click();
          assert.equal(
            await page.locator(".phone-screen").getAttribute("data-theme"),
            "dark",
          );
          await page
            .getByRole("switch", { name: "Hareketi azalt", exact: true })
            .click();
          await page.reload({ waitUntil: "networkidle" });
          assert.equal(
            await page.locator(".lab.theme-dark.reduced-motion").count(),
            1,
          );
          assert.equal(
            await page
              .getByRole("switch", { name: "Hareketi azalt" })
              .getAttribute("aria-checked"),
            "true",
          );
          await page.screenshot({ path: path.join(cache, "dark-final.png") });
        },
      );
      await t.test(
        "wallpaper choice is real, local and survives reload",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Koleksiyon", exact: true })
            .click();
          await page
            .getByRole("button", {
              name: "Kapadokya ışığı duvar kâğıdını uygula",
              exact: true,
            })
            .click();
          await page.getByRole("button", { name: "Ana ekranda gör" }).click();
          assert.match(
            await page.locator(".phone-screen").getAttribute("style"),
            /cappadocia/,
          );
          await page.reload({ waitUntil: "networkidle" });
          assert.match(
            await page.locator(".phone-screen").getAttribute("style"),
            /cappadocia/,
          );
        },
      );
      await t.test(
        "tasks and notes use real local persistence and Turkish text",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Atölye", exact: true })
            .click();
          await page.getByRole("button", { name: /^Günüm/ }).click();
          await page
            .getByRole("textbox", { name: "Yeni görev" })
            .fill("İstanbul için yeni bir fikir");
          await page.getByRole("button", { name: "Görev ekle" }).click();
          await page
            .getByRole("checkbox", {
              name: "İstanbul için yeni bir fikir tamamlandı",
              exact: true,
            })
            .click();
          await page.reload({ waitUntil: "networkidle" });
          await page.getByRole("button", { name: /^Günüm/ }).click();
          assert.equal(
            await page
              .getByRole("checkbox", {
                name: "İstanbul için yeni bir fikir tamamlandı",
              })
              .getAttribute("aria-checked"),
            "true",
          );
          await page
            .getByRole("button", { name: "Ana ekrana dön", exact: true })
            .click();
          await page.getByRole("button", { name: /^Defter/ }).click();
          await page
            .getByRole("textbox", { name: "Defter notu" })
            .fill("Merhaba, Rıfkı. Işık, çay ve İstanbul.");
          await page.reload({ waitUntil: "networkidle" });
          await page.getByRole("button", { name: /^Defter/ }).click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Defter notu" })
              .inputValue(),
            "Merhaba, Rıfkı. Işık, çay ve İstanbul.",
          );
        },
      );
      await t.test(
        "calculator executes arithmetic, not source code, and all sixteen tool entries exist",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Atölye", exact: true })
            .click();
          assert.equal(await page.locator(".tool-card").count(), 16);
          await page.screenshot({
            path: path.join(cache, "atelier-final.png"),
          });
          await page.getByRole("button", { name: /^Hesap/ }).click();
          await page
            .getByRole("textbox", { name: "Hesap ifadesi" })
            .fill("(24 + 18) × 2");
          await page
            .getByRole("button", { name: "Hesapla", exact: true })
            .click();
          assert.equal(
            await page.locator(".result-card pre").textContent(),
            "84",
          );
          await page
            .getByRole("textbox", { name: "Hesap ifadesi" })
            .fill("alert(1)");
          await page
            .getByRole("button", { name: "Hesapla", exact: true })
            .click();
          assert.equal(await page.getByRole("alert").isVisible(), true);
        },
      );
      await t.test(
        "local Rifki sends no request, honestly identifies itself and waits for action confirmation",
        async () => {
          await fresh();
          await page.locator(".home-rifki").click();
          const before = requests.filter((x) =>
            x.includes("/api/rifki/chat"),
          ).length;
          await page
            .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
            .fill("Koyu görünüme geç");
          await page.getByRole("button", { name: "Mesajı gönder" }).click();
          assert.equal(await page.locator(".lab.theme-light").count(), 1);
          await page
            .getByRole("button", { name: "Koyu görünümü uygula" })
            .click();
          assert.equal(await page.locator(".lab.theme-dark").count(), 1);
          assert.equal(
            requests.filter((x) => x.includes("/api/rifki/chat")).length,
            before,
          );
          await page
            .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
            .fill("Sen bir yapay zekâ mısın?");
          await page.getByRole("button", { name: "Mesajı gönder" }).click();
          assert.equal(
            await page.getByText(/kural tabanlı çevrimdışı rehber/).isVisible(),
            true,
          );
          await page.screenshot({ path: path.join(cache, "rifki-final.png") });
          await page
            .getByRole("button", { name: "Model", exact: true })
            .click();
          await page
            .getByText("Üretken model bağlı değil", { exact: true })
            .waitFor();
          assert.equal(
            await page
              .getByRole("button", { name: "Yeni model sohbeti aç" })
              .count(),
            0,
          );
          await page.getByRole("button", { name: "Pencereyi kapat" }).click();
        },
      );
      await t.test(
        "model UI requires consent and never uploads the preceding local conversation (mock transport only)",
        async () => {
          await fresh();
          await page.locator(".home-rifki").click();
          await page
            .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
            .fill("Yalnız yerelde kalan örnek");
          await page.getByRole("button", { name: "Mesajı gönder" }).click();
          let captured;
          await page.route("**/api/rifki/status", (route) =>
            route.fulfill({ json: { enabled: true, label: "Fixture modeli" } }),
          );
          await page.route("**/api/rifki/chat", (route) => {
            captured = route.request().postDataJSON();
            return route.fulfill({
              json: {
                text: "Bu yalnız taşıma testi yanıtıdır.",
                mode: "model",
                label: "Fixture modeli",
              },
            });
          });
          try {
            await page
              .getByRole("button", { name: "Model", exact: true })
              .click();
            const enable = page.getByRole("button", {
              name: "Yeni model sohbeti aç",
            });
            await enable.waitFor();
            assert.equal(await enable.isDisabled(), true);
            await page.getByRole("checkbox").check();
            await enable.click();
            await page
              .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
              .fill("Yeni model sohbeti");
            await page.getByRole("button", { name: "Mesajı gönder" }).click();
            await page.getByText("Bu yalnız taşıma testi yanıtıdır.").waitFor();
            assert.equal(captured.consent, true);
            assert.deepEqual(captured.messages, [
              { role: "user", content: "Yeni model sohbeti" },
            ]);
          } finally {
            await page.unroute("**/api/rifki/status");
            await page.unroute("**/api/rifki/chat");
          }
        },
      );
      await t.test(
        "APK review hashes actual selected bytes, rejects non-APK and never claims installation",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Mağaza", exact: true })
            .click();
          await page
            .getByRole("button", { name: "APK incele", exact: true })
            .click();
          const input = page.getByLabel("İncelemek için APK seç");
          await input.setInputFiles({
            name: "yanlis.exe",
            mimeType: "application/octet-stream",
            buffer: Buffer.from([0x50, 0x4b, 3, 4, 0, 0, 0, 0]),
          });
          assert.match(
            await page.getByRole("alert").textContent(),
            /\.apk dosyası seç/,
          );
          const bytes = Buffer.from([0x50, 0x4b, 3, 4, 0, 0, 0, 0]);
          await input.setInputFiles({
            name: "ornek.apk",
            mimeType: "application/vnd.android.package-archive",
            buffer: bytes,
          });
          const hash = crypto.createHash("sha256").update(bytes).digest("hex");
          await page.getByText(hash, { exact: true }).waitFor();
          assert.equal(
            await page.getByText(/Bu sonuç APK yapısını/).isVisible(),
            true,
          );
          assert.equal(
            await page.getByRole("button", { name: /^Kur$|^Yükle$/ }).count(),
            0,
          );
        },
      );
      await t.test(
        "wishlist survives reload, source review is explicit, and Google links are external HTTPS",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Mağaza", exact: true })
            .click();
          await page
            .getByRole("button", {
              name: "Firefox istek listesine ekle",
              exact: true,
            })
            .click();
          await page.reload({ waitUntil: "networkidle" });
          await page
            .getByRole("button", { name: "İstek listem", exact: true })
            .click();
          assert.equal(await page.locator(".store-item").count(), 1);
          await page
            .getByRole("button", { name: "İncele", exact: true })
            .click();
          assert.equal(
            await page
              .getByRole("link", { name: "Resmî geliştiriciye git" })
              .getAttribute("target"),
            "_blank",
          );
          await page.getByRole("button", { name: "Pencereyi kapat" }).click();
          await home();
          await page
            .getByRole("button", { name: "Google", exact: true })
            .click();
          const links = await page
            .locator(".google-grid a")
            .evaluateAll((nodes) =>
              nodes.map((a) => ({
                href: a.href,
                target: a.target,
                rel: a.rel,
              })),
            );
          assert.equal(links.length, 6);
          assert.ok(
            links.every(
              (a) =>
                a.href.startsWith("https:") &&
                a.target === "_blank" &&
                a.rel.includes("noreferrer"),
            ),
          );
          assert.equal(
            await page
              .getByText(/kurulu Google uygulamaları değildir/)
              .isVisible(),
            true,
          );
        },
      );
      await t.test(
        "reading list, read-state and real TXT export work on explicitly sample content",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Haber", exact: true })
            .click();
          assert.equal(
            await page.getByText(/özgün örnek metinler/).isVisible(),
            true,
          );
          await page
            .locator(".article-card")
            .first()
            .getByRole("button", { name: /kitaplığa ekle/ })
            .click();
          await page
            .getByRole("button", { name: "Kitaplığım", exact: true })
            .click();
          assert.equal(await page.locator(".article-card").count(), 1);
          await page.locator(".article-open").first().click();
          assert.equal(await page.getByRole("dialog").isVisible(), true);
          const downloading = page.waitForEvent("download");
          await page
            .getByRole("button", { name: "TXT olarak dışa aktar" })
            .click();
          const download = await downloading;
          assert.equal(download.suggestedFilename(), "slow-city.txt");
          const output = await fs.readFile(await download.path(), "utf8");
          assert.match(output, /özgün bir okuma örneğidir/);
          await page.getByRole("button", { name: "Pencereyi kapat" }).click();
          await page
            .getByRole("button", { name: "Okunmamış", exact: true })
            .click();
          assert.equal(await page.locator(".article-card").count(), 2);
        },
      );
      await t.test(
        "small screens, reduced-motion and keyboard accessibility structure",
        async () => {
          await fresh(320, 640);
          assert.equal(
            await page.evaluate(
              () => document.documentElement.scrollWidth === innerWidth,
            ),
            true,
          );
          await page.emulateMedia({ reducedMotion: "reduce" });
          await page
            .getByRole("button", { name: "Nazar boncuğu güç menüsü" })
            .click();
          assert.equal(
            await page
              .locator(".sheet")
              .evaluate((e) => getComputedStyle(e).animationName),
            "none",
          );
          await page.keyboard.press("Escape");
          await page.setViewportSize({ width: 390, height: 844 });
          await page
            .getByRole("button", { name: "Ayarlar", exact: true })
            .click();
          const audit = await new AxeBuilder({ page }).analyze();
          assert.deepEqual(
            audit.violations
              .filter((v) => ["critical", "serious"].includes(v.impact))
              .map((v) => ({ id: v.id, description: v.description })),
            [],
          );
          await page.emulateMedia({ reducedMotion: "no-preference" });
        },
      );
      await t.test(
        "corrupt local record is preserved until an explicit destructive reset",
        async () => {
          await fresh();
          await page.evaluate(
            (key) => localStorage.setItem(key, "{corrupt"),
            KEY,
          );
          await page.reload({ waitUntil: "networkidle" });
          assert.equal(await page.locator(".storage-error").isVisible(), true);
          assert.equal(
            await page.evaluate((key) => localStorage.getItem(key), KEY),
            "{corrupt",
          );
          await page.locator(".storage-error").click();
          await page
            .getByRole("button", { name: "Vazgeç", exact: true })
            .click();
          assert.equal(
            await page.evaluate((key) => localStorage.getItem(key), KEY),
            "{corrupt",
          );
          await page.locator(".storage-error").click();
          await page
            .getByRole("button", {
              name: "Evet, yalnız önizleme verilerini temizle",
            })
            .click();
          assert.equal(await page.locator(".storage-error").count(), 0);
          assert.equal(
            JSON.parse(
              await page.evaluate((key) => localStorage.getItem(key), KEY),
            ).version,
            1,
          );
        },
      );
      await t.test(
        "storage denial is visible and does not disable the session",
        async () => {
          await fresh();
          await page.evaluate(() => localStorage.clear());
          await page.addInitScript((key) => {
            const original = Storage.prototype.setItem;
            Storage.prototype.setItem = function (k, v) {
              if (k === key)
                throw new DOMException(
                  "Test storage blocked",
                  "QuotaExceededError",
                );
              return original.call(this, k, v);
            };
          }, KEY);
          await page.reload({ waitUntil: "networkidle" });
          assert.equal(await page.locator(".storage-error").isVisible(), true);
          await page
            .getByRole("button", { name: "Atölye", exact: true })
            .click();
          await page.getByRole("button", { name: /^Hesap/ }).click();
          await page
            .getByRole("textbox", { name: "Hesap ifadesi" })
            .fill("2+2");
          await page
            .getByRole("button", { name: "Hesapla", exact: true })
            .click();
          assert.equal(
            await page.locator(".result-card pre").textContent(),
            "4",
          );
        },
      );
      assert.deepEqual(errors, [], "No uncaught React/browser errors");
    } finally {
      await context.close();
      await browser.close();
    }
  },
);
