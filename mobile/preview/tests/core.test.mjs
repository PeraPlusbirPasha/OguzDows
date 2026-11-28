import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createHash } from "node:crypto";
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
  // The legacy CI field aggregates both Java and Kotlin JVM reports.
  assert.deepEqual(sdk.java_unit_tests, {
    tests: 20,
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
test("connected claims require same-source 24-case acceptance, independent TLS/capture receipts and package evidence; old pixels stay historical", () => {
  // This checks recorded evidence consistency, not a local APK/device execution.
  const read = (name) =>
    JSON.parse(fs.readFileSync(new URL(`../../${name}`, import.meta.url)));
  const parity = read("feature-parity.json");
  const sdk = read(parity.native_evidence.sdk_report);
  const emulator = read(parity.native_evidence.emulator_report);
  const pkg = read(parity.native_evidence.package_report);
  const acceptance = read(parity.native_evidence.acceptance_report);
  assert.equal(parity.phase, "connected-shell-api35-emulator-accepted");
  assert.equal(parity.native_emulator_verified, emulator.passed);
  assert.equal(emulator.passed, true);
  assert.equal(emulator.emulator_only, true);
  for (const report of [sdk, pkg, acceptance]) {
    assert.equal(report.source_sha, emulator.source_sha);
    assert.equal(report.github.run_url, emulator.github.run_url);
  }
  assert.equal(emulator.source_sha, parity.native_evidence.source_sha);
  assert.equal(emulator.source_sha, parity.native_connected.source_sha);
  const required = {
    ...Object.fromEntries(
      [
        "bundledBridgeRolesValidationAndIsolation",
        "paidActionsRequireFinalNativeConsent",
        "systemVolumeBrightnessAndNativeThemeAreReal",
        "incomingSmsUsesTheRealProviderAndRichInbox",
        "outgoingSmsWaitsForActualSentCallback",
        "outgoingCallUsesTelecomAndOurInCallService",
        "incomingCallCanBeAnsweredMutedAndEndedInOurUi",
        "localApkReviewCancelAndSystemInstall",
      ].map((name) => [`NativeDeviceTest.${name}`, 1]),
    ),
    "LauncherDeviceTest.suite": 5,
    "ConnectedDeviceTest.suite": 4,
    "BridgeDeviceTest.nativeTls": 1,
    "BridgeDeviceTest.pcArmInterop": 1,
    "BridgeDeviceTest.systemProjection": 1,
    "RepositorySecurityTest.suite": 3,
    "LiveRepositoryTest.suite": 1,
  };
  assert.equal(emulator.tests.length, 15);
  assert.equal(new Set(emulator.tests.map((t) => t.name)).size, 15);
  assert.deepEqual(
    Object.fromEntries(emulator.tests.map((t) => [t.name, t.test_cases])),
    required,
  ); // No communications/installer/launcher/connected/capture coverage may disappear.
  assert.ok(emulator.tests.every((t) => t.passed && !t.failure && !t.error));
  assert.equal(parity.android_acceptance.driver_selections_required, 15);
  assert.equal(parity.android_acceptance.instrumentation_cases_required, 24);
  assert.equal(
    parity.android_acceptance.instrumentation_cases_observed_passed,
    24,
  );
  assert.equal(parity.android_acceptance.driver_selections_observed_passed, 15);
  assert.equal(parity.android_acceptance.jvm_unit_tests_observed_passed, 20);
  assert.equal(acceptance.passed, true);
  assert.equal(acceptance.native_cases, 24);
  assert.equal(acceptance.jvm_cases, 20);
  assert.equal(acceptance.interop_files, 4);
  assert.equal(acceptance.physical_devices_tested, false);
  assert.equal(acceptance.rom_or_gms_certification, false);
  const fileHashes = Object.fromEntries(
    Object.entries({
      "native-to-desktop.txt": "native-host to desktop-client fixture\n",
      "desktop-upload.txt": "desktop-client to native-host fixture\n",
      "desktop-to-native.txt": "desktop-host to native-client fixture\n",
      "native-upload.txt": "native-client to desktop-host fixture\n",
    }).map(([name, bytes]) => [
      name,
      createHash("sha256").update(bytes).digest("hex"),
    ]),
  );
  for (const peer of [emulator.device_bridge, emulator.native_device_bridge]) {
    assert.equal(peer.protocol, 1);
    for (const flag of [
      "native_host_python_client",
      "python_host_native_client",
      "pinned_tls",
      "sha256_verified",
    ])
      assert.equal(peer[flag], true);
    assert.equal(peer.files_verified, 4);
    assert.deepEqual(peer.file_sha256, fileHashes);
    assert.equal(peer.physical_devices, false);
  }
  for (const flag of [
    "media_projection_consent",
    "cancel_tested",
    "foreground_service",
    "fixture_only",
    "stop_tested",
  ])
    assert.equal(emulator.screen_capture[flag], true);
  assert.equal(emulator.screen_capture.remote_input, false);
  assert.match(emulator.screen_capture.sha256, /^[a-f0-9]{64}$/);
  assert.ok(emulator.screen_capture.frame_bytes > 0);
  assert.ok(emulator.screen_capture.frame_bytes <= 512 * 1024);
  assert.equal(acceptance.real_capture_sha256, emulator.screen_capture.sha256);
  assert.equal(
    parity.native_connected.media_projection.sha256,
    emulator.screen_capture.sha256,
  );
  assert.equal(
    parity.native_connected.media_projection.frame_bytes,
    emulator.screen_capture.frame_bytes,
  );
  assert.equal(parity.native_connected.global_systemui_replaced, false);
  assert.equal(parity.native_connected.secure_keyguard_replaced, false);
  assert.equal(parity.native_connected.physical_pc_phone_arm_tested, false);
  assert.equal(parity.native_connected.permanent_anr_resolution_proven, false);
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
  assert.equal(pkg.version, "0.4.0-connected");
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
  assert.equal(pkg.local_retrieval.completed, false);
  assert.equal(emulator.local_visual_retrieval.complete, false);
  assert.equal(parity.native_launcher.emulator_verified, true);
  assert.equal(parity.native_launcher.cloud_voice_wake_word_implemented, false);
  assert.equal(parity.native_launcher.physical_ram_fps_power_measured, false);
  const review = emulator.tests.find(
    (t) => t.name === "NativeDeviceTest.localApkReviewCancelAndSystemInstall",
  );
  assert.equal(
    parity.native_connected.known_emulator_main_thread_stall_ms,
    review.main_thread_stall.main_delay_ms,
  );
  assert.match(
    review.main_thread_stall.main,
    /HardwareRenderer.nSyncAndDrawFrame/,
  );
  const oldLauncher = parity.native_evidence.historical_accepted_0_3;
  const oldEmulator = read(oldLauncher.emulator_report);
  assert.equal(oldEmulator.source_sha, oldLauncher.source_sha);
  assert.equal(oldEmulator.passed, true);
  assert.equal(
    oldEmulator.tests.reduce((sum, t) => sum + t.test_cases, 0),
    17,
  );
  // Existing pixels remain valid historical 0.3 evidence, NEVER a borrowed 0.4 capture.
  assert.equal(
    parity.native_launcher.visual_preview_source_sha,
    oldLauncher.source_sha,
  );
  assert.notEqual(
    parity.native_launcher.visual_preview_source_sha,
    emulator.source_sha,
  );
  assert.match(parity.native_launcher.visual_scope, /Historical accepted 0\.3/);
  const preview = fs.readFileSync(
    new URL(`../../${parity.native_launcher.visual_preview}`, import.meta.url),
  );
  assert.equal(
    createHash("sha256").update(preview).digest("hex"),
    oldEmulator.visual_preview.sha256,
  );
  assert.deepEqual([...preview.subarray(0, 3)], [0xff, 0xd8, 0xff]);
  assert.equal(oldEmulator.visual_preview.width, 234);
  assert.equal(oldEmulator.visual_preview.height, 520);
  const baseline = parity.native_evidence.historical_accepted_0_2;
  assert.equal(read(baseline.emulator_report).passed, true);
  assert.equal(read(baseline.emulator_report).source_sha, baseline.source_sha);
  assert.equal(
    read(baseline.emulator_report).tests.reduce(
      (sum, t) => sum + t.test_cases,
      0,
    ),
    12,
  );
  for (const failed of [
    ...parity.native_evidence.historical_failed_emulator_reports,
    ...parity.native_evidence.historical_partial_failed_reports,
  ])
    assert.equal(read(failed).passed, false); // Never rewrite failed history.
  for (const flag of [
    "physical_sim_tested",
    "emergency_calls_tested",
    "gms_certification_tested",
    "product_anr_detected",
    "product_crash_detected",
  ])
    assert.equal(emulator[flag], false);
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
