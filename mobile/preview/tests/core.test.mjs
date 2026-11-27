import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  calculate,
  contrast,
  convert,
  initialState,
  restoreState,
  normalize,
  localReply,
  inspectApkHeader,
  sha256,
  allowedHttps,
  TOOLS,
} from "../src/core.mjs";

test("Turkish normalization preserves dotted/dotless search semantics", () => {
  assert.equal(normalize("İSTANBUL, IŞIK, RIFKI"), "istanbul, isik, rifki");
  assert.equal(normalize("x".repeat(3000)).length, 2000);
});
test("all sixteen desktop tools are represented and ten really interactive", () => {
  assert.equal(TOOLS.length, 16);
  assert.equal(new Set(TOOLS.map((x) => x.id)).size, 16);
  assert.equal(TOOLS.filter((x) => x.interactive).length, 10);
  const parity = JSON.parse(
    fs.readFileSync(new URL("../../feature-parity.json", import.meta.url)),
  );
  assert.deepEqual(
    parity.workbench.map((x) => x.id),
    TOOLS.map((x) => x.id),
  );
  assert.equal(parity.other_seven_new_functions.length, 7);
  assert.equal(parity.rom_built, false);
  assert.equal(parity.native_apk_built, true);
  const sdk = JSON.parse(
    fs.readFileSync(
      new URL(`../../${parity.native_evidence.sdk_report}`, import.meta.url),
    ),
  );
  assert.match(sdk.source_sha, /^[a-f0-9]{40}$/);
  assert.deepEqual(sdk.java_unit_tests, {
    tests: 6,
    failures: 0,
    errors: 0,
    skipped: 0,
  });
  assert.equal(sdk.lint.Error || 0, 0);
  assert.equal(sdk.emulator_passed, null); // APK assembly is not proof of device acceptance.
  assert.equal(typeof parity.native_emulator_verified, "boolean");
  assert.equal(parity.physical_device_tested, false);
  assert.equal(parity.live_generative_model_tested, false);
});
test("native emulator claims require matching observed SDK, full device gate and artifact evidence", () => {
  const read = (name) =>
    JSON.parse(fs.readFileSync(new URL(`../../${name}`, import.meta.url)));
  const parity = read("feature-parity.json");
  const sdk = read(parity.native_evidence.sdk_report);
  const emulator = read(parity.native_evidence.emulator_report);
  const pkg = read(parity.native_evidence.package_report);
  assert.equal(parity.native_emulator_verified, emulator.passed);
  assert.equal(emulator.passed, true);
  assert.equal(emulator.emulator_only, true);
  assert.equal(emulator.source_sha, sdk.source_sha);
  assert.equal(emulator.source_sha, pkg.source_sha);
  assert.equal(emulator.source_sha, parity.native_evidence.source_sha);
  assert.equal(
    emulator.tests.length,
    parity.android_acceptance.driver_selections_required,
  );
  assert.equal(new Set(emulator.tests.map((t) => t.name)).size, 10);
  assert.ok(emulator.tests.every((t) => t.passed && t.test_cases > 0));
  assert.equal(
    emulator.tests.reduce((sum, t) => sum + t.test_cases, 0),
    12,
  );
  assert.equal(
    parity.android_acceptance.instrumentation_cases_observed_passed,
    12,
  );
  assert.equal(
    parity.android_acceptance.live_repository_acceptance_observed,
    true,
  );
  assert.ok(emulator.live_repository.apps > 0);
  assert.ok(
    emulator.live_repository.compatible > 0 &&
      emulator.live_repository.compatible <= emulator.live_repository.apps,
  );
  assert.match(emulator.live_apk_review, /installed=false$/);
  assert.equal(pkg.github.workflow_conclusion, "success");
  assert.equal(pkg.github.package_and_apksigner_step_conclusion, "success");
  assert.equal(pkg.ci_apksigner_verify_passed, true);
  assert.deepEqual(
    pkg.files.map((f) => [f.bytes, f.sha256]),
    sdk.assembled.map((f) => [f.bytes, f.sha256]),
  );
  assert.equal(pkg.artifact.retention_days, 14);
  assert.match(pkg.artifact.digest, /^sha256:[a-f0-9]{64}$/);
  assert.equal(
    parity.android_acceptance.artifact_download_verified_locally,
    pkg.local_retrieval.independent_apk_hash_or_signature_verification,
  );
  for (const failed of parity.native_evidence
    .historical_failed_emulator_reports) {
    assert.equal(read(failed).passed, false); // A later success must not rewrite failed history.
  }
  assert.equal(emulator.physical_sim_tested, false);
  assert.equal(emulator.emergency_calls_tested, false);
  assert.equal(emulator.gms_certification_tested, false);
  assert.equal(pkg.rom_built, false);
  assert.equal(pkg.production_signing, false);
});
test("preferences round-trip without conversations, model secrets or permissions", () => {
  const p = initialState();
  p.notes = "Çay, ışık, İstanbul";
  p.tasks.push({ id: "a", title: "Deneme", done: true });
  assert.deepEqual(restoreState(JSON.stringify(p)), p);
  assert.equal(restoreState(null).theme, "light");
  assert.equal("chat" in p, false);
  assert.equal("apiKey" in p, false);
});
test("corrupt, unknown and oversized records are rejected, not silently reset", () => {
  for (const input of [
    "{",
    JSON.stringify({ version: 999 }),
    JSON.stringify(null),
    "a".repeat(150001),
  ])
    assert.throws(() => restoreState(input));
});
test("persisted fields are allowlisted, bounded and sanitized", () => {
  const value = {
    ...initialState(),
    theme: "evil",
    wallpaper: "../../secrets",
    brightness: 1000,
    notes: "n".repeat(18000),
    tasks: [null, { id: "a", title: "x".repeat(900), done: "true" }],
    wishlist: ["valid", "valid", 42],
    apiKey: "do-not-copy",
  };
  const out = restoreState(JSON.stringify(value));
  assert.equal(out.theme, "light");
  assert.equal(out.wallpaper, "bosphorus");
  assert.equal(out.brightness, 100);
  assert.equal(out.notes.length, 16384);
  assert.equal(out.tasks.length, 1);
  assert.equal(out.tasks[0].title.length, 180);
  assert.equal(out.tasks[0].done, false);
  assert.deepEqual(out.wishlist, ["valid"]);
  assert.equal("apiKey" in out, false);
});
test("arithmetic honors precedence, unary signs, comma and parentheses", () => {
  assert.equal(calculate("(24 + 18) × 2"), 84);
  assert.equal(calculate("2 + 3 * 4"), 14);
  assert.equal(calculate("-2 * (3 + 0,5)"), -7);
  assert.equal(calculate("10 ÷ 4"), 2.5);
});
test("arithmetic rejects execution, implicit products, malformed syntax and infinity", () => {
  for (const value of [
    "",
    "alert(1)",
    "globalThis.process",
    "2(4)",
    "1 2",
    "2**3",
    "1/0",
    "()",
    "1+",
    "((3)",
    "1.2.3",
    "9".repeat(130),
  ])
    assert.throws(() => calculate(value), value);
  assert.throws(() => calculate("(".repeat(22) + "1" + ")".repeat(22)));
});
test("actual WCAG sRGB contrast and bounded unit conversion", () => {
  assert.equal(contrast("#000000"), 21);
  assert.equal(contrast("#ffffff"), 1);
  assert.ok(contrast("#24675f") > 6);
  assert.throws(() => contrast("red"));
  assert.equal(convert("2", "km-m"), 2000);
  assert.equal(convert("0", "c-f"), 32);
  assert.equal(convert("1", "mib-mb"), 1.048576);
  for (const n of ["", "NaN", "Infinity", "10000000000000"])
    assert.throws(() => convert(n, "km-m"));
  assert.throws(() => convert("-274", "c-f"));
  assert.throws(() => convert("2", "unsupported"));
});
test("APK header check is deliberately NOT package, malware or signing verification", () => {
  const out = inspectApkHeader(
    "ornek.APK",
    8,
    new Uint8Array([0x50, 0x4b, 3, 4]),
  );
  assert.equal(out.signatureVerified, false);
  assert.equal(out.installableHere, false);
  for (const name of ["evil.exe", "bundle.xapk", "split.apks"])
    assert.throws(() => inspectApkHeader(name, 8, [0x50, 0x4b, 3, 4]));
  assert.throws(() =>
    inspectApkHeader("test.apk", 33 * 1024 * 1024, [0x50, 0x4b, 3, 4]),
  );
  assert.throws(() => inspectApkHeader("test.apk", 8, [0, 0, 0, 0]));
});
test("SHA-256 hashes actual bytes, not file names", async () => {
  assert.equal(
    await sha256(new TextEncoder().encode("abc")),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
});
test("local Rifki states its limits and proposes only allowlisted opt-in actions", () => {
  const allowed = new Set([
    "dark",
    "light",
    "apk",
    "google",
    "low-power",
    "notes",
    "tasks",
    "culture",
  ]);
  for (const text of [
    "koyu tema",
    "aydınlık",
    "APK yükle",
    "Google",
    "pil",
    "not",
    "günümü planla",
    "kültür",
  ]) {
    const response = localReply(text);
    assert.ok(allowed.has(response.action), text);
    assert.ok(response.label);
  }
  assert.match(localReply("Sen bir yapay zekâ mısın?").text, /kural tabanlı/);
  assert.equal(localReply("sudo rm -rf /").action, undefined);
  assert.match(localReply("sudo rm -rf /").text, /Komut çalıştırmam/);
  assert.equal(localReply("rastgele soru").action, undefined);
});
test("external links cannot use script, file, data, credentials or insecure HTTP", () => {
  assert.equal(allowedHttps("https://www.google.com/"), true);
  for (const url of [
    "javascript:alert(1)",
    "http://example.com",
    "file:///tmp/a",
    "data:text/html,hello",
    "https://secret:password@example.com",
    "/api/a",
  ])
    assert.equal(allowedHttps(url), false);
});
