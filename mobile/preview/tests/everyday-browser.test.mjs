import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { launchBrowser, cache } from "./browser-helper.mjs";
const BASE = process.env.MOBILE_BASE_URL || "http://127.0.0.1:5173";
const KEY = "oguzdows.mobile.preview.v1";

async function touchSwipe(page, x, y, endX, endY) {
  await page.evaluate(
    ({ x, y, endX, endY }) => {
      const target = document.elementFromPoint(x, y);
      const first = new Touch({
        identifier: 1,
        target,
        clientX: x,
        clientY: y,
      });
      target.dispatchEvent(
        new TouchEvent("touchstart", {
          bubbles: true,
          touches: [first],
          changedTouches: [first],
          targetTouches: [first],
        }),
      );
      const last = new Touch({
        identifier: 1,
        target,
        clientX: endX,
        clientY: endY,
      });
      target.dispatchEvent(
        new TouchEvent("touchend", {
          bubbles: true,
          touches: [],
          changedTouches: [last],
          targetTouches: [],
        }),
      );
    },
    { x, y, endX, endY },
  );
}
async function setRange(locator, value) {
  await locator.evaluate((input, value) => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    ).set.call(input, String(value));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}
function wav() {
  const data = Buffer.alloc(8044);
  data.write("RIFF");
  data.writeUInt32LE(data.length - 8, 4);
  data.write("WAVEfmt ", 8);
  data.writeUInt32LE(16, 16);
  data.writeUInt16LE(1, 20);
  data.writeUInt16LE(1, 22);
  data.writeUInt32LE(8000, 24);
  data.writeUInt32LE(16000, 28);
  data.writeUInt16LE(2, 32);
  data.writeUInt16LE(16, 34);
  data.write("data", 36);
  data.writeUInt32LE(data.length - 44, 40);
  return data;
}

test(
  "daily phone flows, real local media volume, swipe controls and expanded catalog",
  { timeout: 300000 },
  async (t) => {
    const browser = await launchBrowser();
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "tr-TR",
      hasTouch: true,
      acceptDownloads: true,
    });
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    const errors = [],
      external = [],
      network = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => network.push(request.url()));
    await page.route("**/*", (route) => {
      if (new URL(route.request().url()).origin !== new URL(BASE).origin) {
        external.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    let navigation = 0;
    const go = async (screen = "home") => {
      // A changed fragment alone is a same-document navigation, not a reload.
      await page.goto(`${BASE}/?flow=${++navigation}#/${screen}`, {
        waitUntil: "networkidle",
      });
      await page.evaluate(() => document.fonts.ready);
    };
    const fresh = async (screen = "home") => {
      await go();
      await page.evaluate((key) => localStorage.removeItem(key), KEY);
      await go(screen);
    };
    const state = () =>
      page.evaluate((key) => JSON.parse(localStorage.getItem(key)), KEY);
    const controls = () =>
      page
        .getByRole("button", { name: "Denetim merkezini aç", exact: true })
        .click();
    try {
      await t.test(
        "20 launchable app entries and Turkish alias search",
        async () => {
          await fresh("apps");
          assert.equal(
            await page.locator(".drawer-grid .app-tile").count(),
            20,
          );
          await page
            .getByRole("textbox", { name: "Uygulama ara" })
            .fill("rehber");
          assert.equal(await page.locator(".drawer-grid .app-tile").count(), 1);
          await page
            .getByRole("button", { name: "Kişiler", exact: true })
            .click();
          await page
            .getByRole("button", { name: "Kişi ekle", exact: true })
            .waitFor();
          await go("apps");
          await page
            .getByRole("textbox", { name: "Uygulama ara" })
            .fill("hesap makinesi");
          await page
            .getByRole("button", { name: "Hesap", exact: true })
            .click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Hesap ifadesi" })
              .isVisible(),
            true,
          );
        },
      );
      await t.test(
        "home pages really swipe horizontally and pagination opens daily apps",
        async () => {
          await fresh();
          await touchSwipe(page, 310, 480, 100, 482);
          assert.equal(
            await page
              .getByRole("button", { name: "Ana ekran sayfası 2", exact: true })
              .getAttribute("aria-pressed"),
            "true",
          );
          assert.equal(
            await page
              .locator(".home-apps")
              .getByRole("button", { name: "Telefon", exact: true })
              .isVisible(),
            true,
          );
          await touchSwipe(page, 90, 480, 300, 481);
          assert.equal(
            await page
              .getByRole("button", { name: "Ana ekran sayfası 1", exact: true })
              .getAttribute("aria-pressed"),
            "true",
          );
          await page
            .getByRole("button", { name: "Ana ekran sayfası 3", exact: true })
            .click();
          await page
            .locator(".home-apps")
            .getByRole("button", { name: "Hesap", exact: true })
            .click();
          await page.getByRole("textbox", { name: "Hesap ifadesi" }).waitFor();
        },
      );
      await t.test(
        "Rifki only opens daily apps or controls after the suggested button is pressed",
        async () => {
          await fresh("rifki");
          await page
            .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
            .fill("Mesaj yazmak istiyorum");
          await page
            .getByRole("button", { name: "Mesajı gönder", exact: true })
            .click();
          assert.equal(
            await page.getByRole("textbox", { name: "SMS taslağı" }).count(),
            0,
          );
          await page
            .getByRole("button", { name: "Mesajlar’ı aç", exact: true })
            .click();
          await page.getByRole("textbox", { name: "SMS taslağı" }).waitFor();
          await go("rifki");
          await page
            .getByRole("textbox", { name: "Rıfkı’ya mesaj" })
            .fill("Sesi ayarla");
          await page
            .getByRole("button", { name: "Mesajı gönder", exact: true })
            .click();
          await page
            .locator(".chat-log")
            .getByRole("button", { name: "Denetim merkezini aç", exact: true })
            .click();
          await page.getByRole("dialog", { name: "Denetim merkezi" }).waitFor();
        },
      );
      await t.test(
        "home search finds apps, tools, later notes, settings and catalog without upload",
        async () => {
          await fresh();
          await page.evaluate((key) => {
            const saved = JSON.parse(localStorage.getItem(key));
            saved.notes = "a".repeat(5000) + " Işık vapur fikri";
            localStorage.setItem(key, JSON.stringify(saved));
          }, KEY);
          await go();
          await page
            .getByRole("button", { name: "Cihazında ara", exact: true })
            .click();
          const search = page.getByRole("searchbox", {
            name: "Cihazında ara",
            exact: true,
          });
          await search.fill("isik");
          assert.equal(
            await page
              .getByRole("button", { name: /Defter’de eşleşme/ })
              .isVisible(),
            true,
          );
          await search.fill("ses");
          await page
            .getByRole("button", { name: /Ses ve denetim merkezi/ })
            .click();
          assert.equal(
            await page
              .getByRole("dialog", { name: "Denetim merkezi" })
              .isVisible(),
            true,
          );
          await page.keyboard.press("Escape");
          await search.fill("84 / 2");
          assert.equal(
            await page.locator(".search-calculation strong").textContent(),
            "= 42",
          );
          await search.fill("signal");
          await page.getByRole("button", { name: /Signal İletişim/ }).click();
          assert.equal(
            await page
              .getByRole("dialog", { name: "Signal", exact: true })
              .isVisible(),
            true,
          );
          assert.equal(external.length, 0);
          assert.equal(
            network.some((url) => url.includes("/api/rifki/chat")),
            false,
          );
        },
      );
      await t.test(
        "dial pad, manual number and call/SMS handoff URIs work without simulating a call",
        async () => {
          await fresh();
          await page
            .getByRole("button", { name: "Telefon seçenekleri", exact: true })
            .click();
          await page
            .getByRole("button", { name: "5 tuşu", exact: true })
            .click();
          await page
            .getByRole("button", { name: "5 tuşu", exact: true })
            .click();
          await page
            .getByRole("button", { name: "5 tuşu", exact: true })
            .click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Aranacak numara" })
              .inputValue(),
            "555",
          );
          await page.getByRole("button", { name: "Son rakamı sil" }).click();
          assert.equal(
            await page
              .getByRole("link", { name: "Arama uygulamasında aç" })
              .getAttribute("href"),
            null,
          );
          await page
            .getByRole("textbox", { name: "Aranacak numara" })
            .fill("+90 (555) 010-00-00");
          assert.equal(
            await page
              .getByRole("link", { name: "Arama uygulamasında aç" })
              .getAttribute("href"),
            "tel:+905550100000",
          );
          assert.equal(await page.getByText(/Arama bağlandı/).count(), 0);
          await page
            .getByRole("button", { name: "Bu numaraya mesaj yaz" })
            .click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Mesaj alıcısı" })
              .inputValue(),
            "+905550100000",
          );
          await page.screenshot({
            path: path.join(cache, "messages-updated.png"),
          });
          await go("phone");
          await page
            .getByRole("textbox", { name: "Aranacak numara" })
            .fill("*#06#");
          assert.equal(
            await page
              .getByRole("link", { name: "Arama uygulamasında aç" })
              .getAttribute("href"),
            null,
          );
        },
      );
      await t.test(
        "contacts create, favorite, persist, search, dial and compose; delete needs confirmation",
        async () => {
          await fresh("contacts");
          await page
            .getByRole("button", { name: "Kişi ekle", exact: true })
            .click();
          await page
            .getByRole("textbox", { name: "Kişi adı", exact: true })
            .fill("Işık Deneme");
          await page
            .getByRole("textbox", { name: "Kişinin telefon numarası" })
            .fill("+90 555 010 00 00");
          await page.getByRole("button", { name: "Kişiyi kaydet" }).click();
          await page
            .getByRole("button", { name: "Işık Deneme favorilere ekle" })
            .click();
          await go("contacts");
          assert.equal(
            await page
              .getByRole("button", { name: "Işık Deneme favorilerden çıkar" })
              .getAttribute("aria-pressed"),
            "true",
          );
          await page
            .getByRole("textbox", { name: "Kişilerde ara" })
            .fill("ISIK");
          assert.equal(await page.locator(".contact-card").count(), 1);
          await page
            .getByRole("button", { name: "Işık Deneme için numara çevir" })
            .click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Aranacak numara" })
              .inputValue(),
            "+905550100000",
          );
          await go("search");
          await page
            .getByRole("searchbox", { name: "Cihazında ara" })
            .fill("isik");
          assert.equal(
            await page
              .getByRole("button", { name: /Işık Deneme.*numara çevir/ })
              .isVisible(),
            true,
          );
          await go("contacts");
          await page
            .getByRole("button", { name: "Işık Deneme için mesaj yaz" })
            .click();
          assert.equal(
            await page
              .getByRole("textbox", { name: "Mesaj alıcısı" })
              .inputValue(),
            "+905550100000",
          );
          await go("contacts");
          await page
            .getByRole("button", { name: "Işık Deneme kişisini düzenle" })
            .click();
          await page
            .getByRole("button", { name: "Kişiyi sil", exact: true })
            .click();
          assert.equal((await state()).contacts.length, 1);
          await page
            .getByRole("button", { name: "Vazgeç", exact: true })
            .click();
          await page
            .getByRole("button", { name: "Kişiyi sil", exact: true })
            .click();
          await page
            .getByRole("button", { name: "Evet, kişiyi sil", exact: true })
            .click();
          assert.equal((await state()).contacts.length, 0);
        },
      );
      await t.test(
        "SMS draft survives reload with safe Turkish body and never claims sent",
        async () => {
          await fresh("messages");
          await page
            .getByRole("textbox", { name: "Mesaj alıcısı" })
            .fill("5550100000");
          await page
            .getByRole("textbox", { name: "SMS taslağı" })
            .fill("İyi günler & görüşelim?#");
          await go("messages");
          assert.equal(
            await page
              .getByRole("textbox", { name: "SMS taslağı" })
              .inputValue(),
            "İyi günler & görüşelim?#",
          );
          const target = await page
            .getByRole("link", { name: "Sistem mesajlaşmasında aç" })
            .getAttribute("href");
          assert.equal(
            target,
            "sms:5550100000?body=%C4%B0yi%20g%C3%BCnler%20%26%20g%C3%B6r%C3%BC%C5%9Felim%3F%23",
          );
          assert.equal(
            await page
              .getByText("TASLAK · GÖNDERİLMEDİ", { exact: true })
              .isVisible(),
            true,
          );
        },
      );
      await t.test(
        "top-edge touch swipe opens top panel, upward handle closes, body scroll does not open it",
        async () => {
          await fresh();
          await touchSwipe(page, 180, 32, 183, 240);
          assert.equal(await page.locator(".sheet-top").count(), 1);
          await page.getByRole("dialog", { name: "Denetim merkezi" }).waitFor();
          const handle = await page
            .getByRole("button", { name: "Paneli kapat", exact: true })
            .boundingBox();
          await page.mouse.move(
            handle.x + handle.width / 2,
            handle.y + handle.height / 2,
          );
          await page.mouse.down();
          await page.mouse.move(handle.x + handle.width / 2, handle.y - 65, {
            steps: 8,
          });
          await page.mouse.up();
          assert.equal(await page.getByRole("dialog").count(), 0);
          await go("apps");
          await touchSwipe(page, 180, 220, 180, 420);
          assert.equal(await page.getByRole("dialog").count(), 0);
          await go();
          await touchSwipe(page, 180, 680, 180, 430);
          await page.getByRole("textbox", { name: "Uygulama ara" }).waitFor();
          await page.mouse.move(190, 25);
          await page.mouse.down();
          await page.mouse.move(190, 210, { steps: 8 });
          await page.mouse.up();
          await page.getByRole("dialog", { name: "Denetim merkezi" }).waitFor();
          await page.screenshot({
            path: path.join(cache, "controls-updated.png"),
          });
        },
      );
      await t.test(
        "panel volume/mute affect actual audio element, brightness dims the preview, settings persist",
        async () => {
          await fresh("media");
          await page
            .getByLabel("Müzik dosyası seç", { exact: true })
            .setInputFiles({
              name: "yerel-deneme.wav",
              mimeType: "audio/wav",
              buffer: wav(),
            });
          await page.waitForFunction(
            () => document.querySelector("audio")?.readyState >= 1,
          );
          await controls();
          await page
            .getByRole("button", { name: "Sesi azalt", exact: true })
            .click();
          await page
            .getByRole("button", { name: "Sesi azalt", exact: true })
            .click();
          assert.equal(
            await page.locator("audio").evaluate((el) => el.volume),
            0.35,
          );
          await page
            .getByRole("button", { name: "Sesi kapat", exact: true })
            .click();
          assert.equal(
            await page.locator("audio").evaluate((el) => el.muted),
            true,
          );
          await setRange(
            page.getByRole("slider", { name: "Önizleme parlaklığı" }),
            30,
          );
          assert.equal((await state()).brightness, 30);
          assert.ok(
            Number(
              await page
                .locator(".phone-dimmer")
                .evaluate((el) => el.style.opacity),
            ) > 0.5,
          );
          await page
            .getByRole("button", { name: "Sesi aç", exact: true })
            .click();
          assert.equal(
            await page.locator("audio").evaluate((el) => el.muted),
            false,
          );
          await page.keyboard.press("Escape");
          await go();
          await controls();
          assert.equal(
            await page
              .getByRole("slider", { name: "Medya sesi", exact: true })
              .inputValue(),
            "35",
          );
          assert.equal(
            await page
              .getByRole("slider", { name: "Önizleme parlaklığı" })
              .inputValue(),
            "30",
          );
          assert.equal((await state()).volume, 35);
        },
      );
      await t.test(
        "24 local recognizable app icons render, categories filter and F-Droid has no invented Play link",
        async () => {
          await fresh("store");
          assert.equal(await page.locator(".store-item").count(), 24);
          assert.equal(
            await page
              .getByRole("group", { name: "Mağaza kategorileri" })
              .getByRole("button")
              .count(),
            9,
          );
          await page.waitForFunction(
            () =>
              [...document.querySelectorAll(".store-item img")].length === 24 &&
              [...document.querySelectorAll(".store-item img")].every(
                (img) => img.complete && img.naturalWidth > 0,
              ),
          );
          const urls = await page
            .locator(".store-item img")
            .evaluateAll((images) => images.map((img) => img.src));
          assert.ok(
            urls.every((url) =>
              url.startsWith(`${new URL(BASE).origin}/assets/apps/`),
            ),
          );
          await page.screenshot({
            path: path.join(cache, "store-updated.png"),
          });
          await page
            .getByRole("button", { name: "İletişim", exact: true })
            .click();
          assert.equal(await page.locator(".store-item").count(), 6);
          await page.getByRole("button", { name: "Tümü", exact: true }).click();
          await page
            .getByRole("textbox", { name: "Mağaza kataloğunda ara" })
            .fill("F-Droid");
          assert.equal(await page.locator(".store-item").count(), 1);
          await page
            .getByRole("button", { name: "İncele", exact: true })
            .click();
          assert.equal(
            await page
              .getByRole("link", { name: "Google Play sayfası" })
              .count(),
            0,
          );
          assert.equal(
            await page
              .getByRole("link", { name: "Resmî geliştiriciye git" })
              .getAttribute("href"),
            "https://f-droid.org/",
          );
        },
      );
      await t.test(
        "calendar month navigation and selected-day local plans persist",
        async () => {
          await fresh("calendar");
          const selected = await page
            .locator(".calendar-grid button[aria-pressed=true]")
            .getAttribute("aria-label");
          await page
            .getByRole("textbox", { name: "Yeni takvim planı" })
            .fill("Bir çay molası");
          await page.getByRole("button", { name: "Plan ekle" }).click();
          await go("calendar");
          assert.equal(
            await page
              .locator(".agenda-list")
              .getByText("Bir çay molası")
              .isVisible(),
            true,
          );
          await page.getByRole("button", { name: "Sonraki ay" }).click();
          await page.getByRole("button", { name: "Önceki ay" }).click();
          assert.equal(
            await page
              .getByRole("button", { name: selected, exact: true })
              .getAttribute("aria-pressed"),
            "true",
          );
          assert.equal((await state()).events.length, 1);
          await page
            .getByRole("button", { name: "Bir çay molası planını sil" })
            .click();
          assert.equal((await state()).events.length, 0);
        },
      );
      await t.test(
        "stopwatch and timer retain start/deadline across navigation without claiming an alarm",
        async () => {
          await fresh("clock");
          await page
            .getByRole("button", { name: "Başlat", exact: true })
            .click();
          assert.ok((await state()).stopwatch.startedAt);
          await go("home");
          await go("clock");
          await page
            .getByRole("button", { name: "Duraklat", exact: true })
            .click();
          assert.ok((await state()).stopwatch.elapsed > 0);
          await page
            .getByRole("button", { name: "Sayaç", exact: true })
            .click();
          await page
            .getByRole("spinbutton", { name: "Sayaç süresi dakika" })
            .fill("1");
          await page
            .getByRole("button", { name: "Sayacı başlat", exact: true })
            .click();
          const deadline = (await state()).timerEnd;
          assert.ok(deadline > Date.now());
          await go("home");
          await go("clock");
          await page
            .getByRole("button", { name: "Sayaç", exact: true })
            .click();
          assert.equal((await state()).timerEnd, deadline);
          await page
            .getByRole("button", { name: "Sayacı iptal et", exact: true })
            .click();
          assert.equal((await state()).timerEnd, null);
        },
      );
      await t.test(
        "browser validates URLs locally and only offers explicit safe external navigation",
        async () => {
          await fresh("browser");
          const input = page.getByRole("searchbox", {
            name: "Web adresi veya arama",
          });
          await input.fill("javascript:alert(1)");
          assert.equal(
            await page
              .getByRole("button", { name: "Webde aç", exact: true })
              .isDisabled(),
            true,
          );
          await input.fill("İstanbul vapur");
          assert.equal(
            await page.locator(".browser-target").getAttribute("href"),
            "https://www.google.com/search?q=%C4%B0stanbul%20vapur",
          );
          await input.fill("example.org");
          assert.equal(
            await page.locator(".browser-target").getAttribute("href"),
            "https://example.org/",
          );
          assert.equal(external.length, 0);
          assert.equal(await page.locator("iframe").count(), 0);
        },
      );
      await t.test(
        "gallery shows only selected real bytes, downloads them, removes local preview and does not upload",
        async () => {
          await fresh("gallery");
          const bytes = Buffer.from(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=",
            "base64",
          );
          await page
            .getByLabel("Galeriye fotoğraf seç", { exact: true })
            .setInputFiles({
              name: "benim-fotografim.png",
              mimeType: "image/png",
              buffer: bytes,
            });
          await page
            .getByRole("button", {
              name: "benim-fotografim.png fotoğrafını aç",
            })
            .click();
          await page.waitForFunction(
            () => document.querySelector(".photo-preview")?.naturalWidth === 1,
          );
          const downloading = page.waitForEvent("download");
          await page.getByRole("link", { name: "Görseli indir" }).click();
          const download = await downloading;
          assert.equal(download.suggestedFilename(), "benim-fotografim.png");
          assert.deepEqual(await fs.readFile(await download.path()), bytes);
          await page
            .getByRole("button", { name: "Önizlemeden kaldır", exact: true })
            .click();
          assert.equal(
            await page
              .getByRole("button", {
                name: "benim-fotografim.png fotoğrafını aç",
              })
              .count(),
            0,
          );
          assert.equal(external.length, 0);
        },
      );
      await t.test(
        "all new routes fit 320px, representative new pages/control panel pass serious axe rules",
        async () => {
          await fresh();
          await page.setViewportSize({ width: 320, height: 640 });
          for (const screen of [
            "apps",
            "search",
            "phone",
            "messages",
            "contacts",
            "calendar",
            "clock",
            "media",
            "browser",
            "gallery",
            "store",
            "notes",
            "tasks",
            "calculator",
          ]) {
            await go(screen);
            assert.equal(
              await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth,
              ),
              true,
              screen,
            );
            assert.equal(
              await page
                .locator(".phone-screen")
                .evaluate((el) => el.scrollWidth <= el.clientWidth),
              true,
              screen,
            );
          }
          await page.setViewportSize({ width: 390, height: 844 });
          for (const screen of [
            "phone",
            "messages",
            "contacts",
            "calendar",
            "store",
            "search",
          ]) {
            await go(screen);
            const audit = await new AxeBuilder({ page }).analyze();
            assert.deepEqual(
              audit.violations
                .filter((v) => ["critical", "serious"].includes(v.impact))
                .map((v) => ({
                  id: v.id,
                  targets: v.nodes.map((n) => n.target),
                })),
              [],
              screen,
            );
          }
          await controls();
          const audit = await new AxeBuilder({ page }).analyze();
          assert.deepEqual(
            audit.violations
              .filter((v) => ["critical", "serious"].includes(v.impact))
              .map((v) => ({
                id: v.id,
                targets: v.nodes.map((n) => n.target),
              })),
            [],
            "control panel",
          );
        },
      );
      await t.test(
        "added animations respect both system reduced motion and low-resource preference",
        async () => {
          await fresh("apps");
          await page.emulateMedia({ reducedMotion: "reduce" });
          assert.equal(
            await page
              .locator(".page-transition")
              .evaluate((el) => getComputedStyle(el).animationName),
            "none",
          );
          await controls();
          assert.equal(
            await page
              .locator(".sheet")
              .evaluate((el) => getComputedStyle(el).animationName),
            "none",
          );
          await page.emulateMedia({ reducedMotion: "no-preference" });
          await page.getByRole("button", { name: /Hafif profil/ }).click();
          assert.equal(
            await page
              .locator(".sheet")
              .evaluate((el) => getComputedStyle(el).animationName),
            "none",
          );
        },
      );
      assert.deepEqual(errors, []);
      assert.deepEqual(external, []);
    } finally {
      await context.close();
      await browser.close();
    }
  },
);
