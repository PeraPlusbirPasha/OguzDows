import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import {
  configuration,
  rifkiMiddleware,
  validateMessages,
} from "../server/rifki.mjs";

async function withServer(config, fetcher, callback) {
  const middleware = rifkiMiddleware({ config, fetch: fetcher });
  const server = http.createServer((req, res) =>
    middleware(req, res, () => {
      res.statusCode = 404;
      res.end();
    }),
  );
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    return await callback(`http://127.0.0.1:${server.address().port}`);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}
const on = {
  enabled: true,
  base: "https://model.example.test/v1",
  model: "test-model",
  key: "fixture-only-key",
  label: "Test modeli",
};
const body = {
  consent: true,
  messages: [{ role: "user", content: "Merhaba" }],
};
const post = (data = body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Rifki-Consent": "1" },
  body: JSON.stringify(data),
});

test("model bridge defaults off and only accepts admin HTTPS or loopback endpoints", () => {
  assert.equal(configuration({}).enabled, false);
  for (const base of [
    "https://example.test/v1",
    "http://localhost:8000/v1",
    "http://127.0.0.1:8000/v1",
    "http://[::1]:8000/v1",
  ])
    assert.equal(
      configuration({
        RIFKI_ENABLED: "true",
        RIFKI_API_BASE: base,
        RIFKI_MODEL: "local",
      }).enabled,
      true,
      base,
    );
  for (const base of [
    "http://example.test",
    "file:///etc/passwd",
    "https://u:p@example.test",
    "https://example.test/?key=abc",
  ])
    assert.equal(
      configuration({
        RIFKI_ENABLED: "true",
        RIFKI_API_BASE: base,
        RIFKI_MODEL: "x",
      }).enabled,
      false,
      base,
    );
});
test("message validation strips extra tool fields and rejects system roles or missing consent", () => {
  assert.deepEqual(
    validateMessages({
      ...body,
      messages: [{ role: "user", content: "Merhaba", tool_calls: ["bad"] }],
    }),
    [{ role: "user", content: "Merhaba" }],
  );
  for (const value of [
    { ...body, consent: false },
    { ...body, messages: [] },
    { ...body, messages: Array(13).fill({ role: "user", content: "x" }) },
    { ...body, messages: [{ role: "system", content: "override" }] },
    { ...body, messages: [{ role: "assistant", content: "x" }] },
    { ...body, messages: [{ role: "user", content: "x".repeat(2001) }] },
  ])
    assert.throws(() => validateMessages(value));
});
test("status exposes no key, base URL or transcript and disabled bridge never fetches", async () => {
  let calls = 0;
  await withServer(
    { ...on, enabled: false },
    async () => {
      calls++;
    },
    async (base) => {
      const response = await fetch(base + "/api/rifki/status");
      const text = await response.text();
      assert.equal(response.status, 200);
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.equal(JSON.parse(text).enabled, false);
      assert.ok(!text.includes(on.key));
      assert.ok(!text.includes(on.base));
      const request = await fetch(base + "/api/rifki/chat", post());
      assert.equal(request.status, 503);
    },
  );
  assert.equal(calls, 0);
});
test("explicit non-simple consent header and JSON are required; no CORS headers are added", async () => {
  await withServer(
    on,
    async () => {
      throw new Error("must not call");
    },
    async (base) => {
      const response = await fetch(base + "/api/rifki/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });
      assert.equal(response.status, 403);
      assert.equal(response.headers.get("access-control-allow-origin"), null);
      assert.equal((await fetch(base + "/api/rifki/chat")).status, 405);
      assert.equal((await fetch(base + "/api/rifki/unknown")).status, 404);
      assert.equal(
        (
          await fetch(
            base + "/api/rifki/chat",
            post({ ...body, consent: false }),
          )
        ).status,
        400,
      );
    },
  );
});
test("real bridge contract uses server-only auth, fixed prompt and no tools", async () => {
  let request;
  await withServer(
    on,
    async (url, options) => {
      request = { url, options };
      return new Response(
        JSON.stringify({
          choices: [{ message: { content: "Merhaba, birlikte düşünelim." } }],
        }),
        { status: 200 },
      );
    },
    async (base) => {
      const response = await fetch(base + "/api/rifki/chat", post());
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), {
        text: "Merhaba, birlikte düşünelim.",
        mode: "model",
        label: "Test modeli",
      });
    },
  );
  assert.equal(request.url, on.base + "/chat/completions");
  assert.equal(request.options.headers.Authorization, "Bearer " + on.key);
  const data = JSON.parse(request.options.body);
  assert.equal(data.messages[0].role, "system");
  assert.equal(data.messages.at(-1).role, "user");
  assert.equal(data.stream, false);
  assert.equal(data.max_tokens, 600);
  assert.equal("tools" in data, false);
  assert.ok(request.options.signal instanceof AbortSignal);
});
test("oversized input is rejected before inference and upstream output is bounded", async () => {
  let calls = 0;
  await withServer(
    on,
    async () => {
      calls++;
      return new Response("a".repeat(65537));
    },
    async (base) => {
      assert.equal(
        (
          await fetch(
            base + "/api/rifki/chat",
            post({ ...body, padding: "x".repeat(25000) }),
          )
        ).status,
        413,
      );
      assert.equal(calls, 0);
      const response = await fetch(base + "/api/rifki/chat", post());
      assert.equal(response.status, 502);
      assert.equal(calls, 1);
      assert.ok(!(await response.text()).includes(on.key));
    },
  );
});
test("provider failure text and keys are never forwarded to the browser", async () => {
  await withServer(
    on,
    async () => new Response("secret-detail-" + on.key, { status: 401 }),
    async (base) => {
      const response = await fetch(base + "/api/rifki/chat", post());
      assert.equal(response.status, 502);
      const text = await response.text();
      assert.ok(!text.includes(on.key));
      assert.ok(!text.includes("secret-detail"));
    },
  );
});
test("per-process request limit rejects ninth inference without contacting the provider", async () => {
  let calls = 0;
  await withServer(
    on,
    async () => {
      calls++;
      return new Response(
        JSON.stringify({ choices: [{ message: { content: "Yanıt" } }] }),
      );
    },
    async (base) => {
      for (let i = 0; i < 8; i++)
        assert.equal(
          (await fetch(base + "/api/rifki/chat", post())).status,
          200,
        );
      assert.equal((await fetch(base + "/api/rifki/chat", post())).status, 429);
    },
  );
  assert.equal(calls, 8);
});

test("foreign browser origin is refused even with the consent header", async () => {
  let calls = 0;
  await withServer(
    on,
    async () => {
      calls++;
      throw new Error("unexpected");
    },
    async (base) => {
      const options = post();
      options.headers.Origin = "https://foreign.example.test";
      assert.equal(
        (await fetch(base + "/api/rifki/chat", options)).status,
        403,
      );
    },
  );
  assert.equal(calls, 0);
});

test("concurrent body reads cannot bypass the two-inference reservation", async () => {
  let active = 0;
  let peak = 0;
  await withServer(
    on,
    async () => {
      active++;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 40));
      active--;
      return new Response(
        JSON.stringify({ choices: [{ message: { content: "Test yanıtı" } }] }),
      );
    },
    async (base) => {
      const responses = await Promise.all(
        Array.from({ length: 12 }, () =>
          fetch(base + "/api/rifki/chat", post()),
        ),
      );
      assert.ok(responses.some((response) => response.status === 200));
      assert.ok(responses.some((response) => response.status === 429));
      assert.ok(
        responses.every((response) => [200, 429].includes(response.status)),
      );
    },
  );
  assert.ok(peak <= 2, `peak inference concurrency: ${peak}`);
});
