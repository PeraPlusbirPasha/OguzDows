import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import crypto from "node:crypto";
import {
  initialState,
  restoreState,
  normalize,
  phoneNumber,
  phoneHref,
  smsHref,
  browserHref,
  validDate,
  swipeAction,
  localReply,
} from "../src/core.mjs";

test("ordinary phone and SMS handoffs reject URI injection, control and service codes", () => {
  assert.equal(phoneNumber("+90 (555) 010-00-00"), "+905550100000");
  assert.equal(phoneHref("+90 555 010 00 00"), "tel:+905550100000");
  assert.equal(phoneHref("112"), "tel:112");
  assert.equal(
    smsHref("5550100000", "İyi günler & nasılsın?#"),
    "sms:5550100000?body=%C4%B0yi%20g%C3%BCnler%20%26%20nas%C4%B1ls%C4%B1n%3F%23",
  );
  assert.equal(smsHref("5550100000"), "sms:5550100000");
  for (const value of [
    "",
    "1",
    "*#06#",
    "tel:555",
    "+90;body=evil",
    "12+345",
    "1".repeat(21),
    "555\n123",
    "555\v123",
    "javascript:alert(1)",
    {},
    null,
  ]) {
    assert.equal(phoneNumber(value), "", String(value));
    assert.equal(phoneHref(value), "");
    assert.equal(smsHref(value), "");
  }
  assert.equal(smsHref("5550100000", "x".repeat(2001)), "");
});
test("web address/search handoffs are explicit safe HTTPS, never iframe or script", () => {
  assert.equal(browserHref("example.org/a?q=1"), "https://example.org/a?q=1");
  assert.equal(browserHref("https://example.org/"), "https://example.org/");
  assert.equal(
    browserHref("İstanbul vapur"),
    "https://www.google.com/search?q=%C4%B0stanbul%20vapur",
  );
  for (const value of [
    "javascript:alert(1)",
    "data:text/html,x",
    "file:///etc/passwd",
    "http://example.org",
    "https://secret:pass@example.org",
    "",
    "x".repeat(501),
  ])
    assert.equal(browserHref(value), "");
});
test("swipes distinguish top-edge controls, app drawer, horizontal and ordinary scrolling", () => {
  assert.equal(swipeAction({ x: 150, y: 25 }, { x: 153, y: 220 }), "quick");
  assert.equal(
    swipeAction({ x: 150, y: 500 }, { x: 153, y: 240 }, { home: true }),
    "apps",
  );
  assert.equal(swipeAction({ x: 150, y: 140 }, { x: 153, y: 340 }), "");
  assert.equal(swipeAction({ x: 150, y: 500 }, { x: 153, y: 240 }), "");
  assert.equal(
    swipeAction({ x: 150, y: 25, blocked: true }, { x: 153, y: 220 }),
    "",
  );
  assert.equal(
    swipeAction({ x: 150, y: 25 }, { x: 153, y: 220 }, { blocked: true }),
    "",
  );
  assert.equal(swipeAction({ x: 150, y: 25 }, { x: 350, y: 80 }), "");
  assert.equal(swipeAction(null, { x: 150, y: 200 }), "");
  assert.equal(
    swipeAction({ x: 300, y: 450 }, { x: 100, y: 451 }, { home: true }),
    "next-page",
  );
  assert.equal(
    swipeAction({ x: 100, y: 450 }, { x: 300, y: 451 }, { home: true }),
    "previous-page",
  );
});
test("old preference records gain safe defaults and new local state is bounded", () => {
  const legacy = restoreState(
    JSON.stringify({ version: 1, notes: "Eski notum" }),
  );
  assert.equal(legacy.notes, "Eski notum");
  assert.equal(legacy.volume, 55);
  assert.equal(legacy.muted, false);
  assert.deepEqual(legacy.contacts, []);
  assert.deepEqual(legacy.events, []);
  const restored = restoreState(
    JSON.stringify({
      ...initialState(),
      volume: 500,
      brightness: -5,
      muted: true,
      contacts: [
        {
          id: "c",
          name: " Işık ",
          number: "+90 555 010 00 00",
          favorite: true,
        },
        { id: "c", name: "dup", number: "123" },
        { id: "bad", name: " ", number: "*#06#" },
      ],
      events: [
        { id: "a", date: "2028-02-29", title: " Gerçek gün " },
        { id: "a", date: "2028-02-29", title: "duplicate" },
        { id: "b", date: "2027-02-29", title: "Olmaz" },
      ],
      messageDraft: {
        number: "1".repeat(100),
        body: "a".repeat(3000),
        sent: true,
      },
      timerEnd: Infinity,
      stopwatch: { elapsed: -1, startedAt: "evil" },
    }),
  );
  assert.equal(restored.volume, 100);
  assert.equal(restored.brightness, 25);
  assert.equal(restored.muted, true);
  assert.deepEqual(restored.contacts, [
    { id: "c", name: "Işık", number: "+905550100000", favorite: true },
  ]);
  assert.deepEqual(restored.events, [
    { id: "a", date: "2028-02-29", title: "Gerçek gün" },
  ]);
  assert.equal(restored.messageDraft.number.length, 40);
  assert.equal(restored.messageDraft.body.length, 2000);
  assert.equal("sent" in restored.messageDraft, false);
  assert.equal(restored.timerEnd, null);
  assert.deepEqual(restored.stopwatch, { elapsed: 0, startedAt: null });
  assert.equal(
    normalize("x".repeat(5000) + "IŞIK", 16384).includes("isik"),
    true,
  );
});
test("calendar rejects impossible and out-of-range dates", () => {
  for (const value of ["2028-02-29", "2026-11-17", "2100-12-31"])
    assert.equal(validDate(value), true);
  for (const value of [
    "2027-02-29",
    "2026-04-31",
    "2026-13-01",
    "1999-01-01",
    "2101-01-01",
    "2026-1-1",
    null,
  ])
    assert.equal(validDate(value), false);
});
test("24 store artworks are local, well-formed, licensed, hashed and network-independent", () => {
  const base = new URL("../public/assets/apps/", import.meta.url);
  const manifest = JSON.parse(
    fs.readFileSync(new URL("manifest.json", base), "utf8"),
  );
  assert.equal(manifest.length, 24);
  assert.equal(new Set(manifest.map((a) => a.id)).size, 24);
  for (const app of manifest) {
    const svg = fs.readFileSync(new URL(`${app.id}.svg`, base), "utf8");
    assert.match(svg, /<svg /);
    assert.match(svg, /<path /);
    assert.match(svg, /<rect /);
    assert.doesNotMatch(svg, /<script|<image|href=|onload=|<foreignObject/i);
    assert.ok(app.source.startsWith("https:"));
    assert.ok(app.license.type);
    assert.equal(app.collection, "simple-icons@15.22.0");
    assert.equal(
      crypto.createHash("sha256").update(svg).digest("hex"),
      app.sha256,
    );
  }
});

test("Rifki daily actions only propose fixed UI navigation, never calls or sends", () => {
  for (const [input, action] of [
    ["mesaj yaz", "messages"],
    ["telefonu aç", "phone"],
    ["rehber", "contacts"],
    ["sesi ayarla", "controls"],
    ["takvim", "calendar"],
    ["müzik", "media"],
    ["kronometre", "clock"],
  ]) {
    const reply = localReply(input);
    assert.equal(reply.action, action);
    assert.ok(reply.label);
  }
});
