import { chromium as playwright } from "playwright-core";
import chromium from "@sparticuz/chromium";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
export const cache = path.join(root, ".cache/mobile");
export async function launchBrowser() {
  const executable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  if (executable)
    return playwright.launch({
      executablePath: executable,
      headless: true,
      args: ["--no-sandbox"],
    });
  // Minimal CI may have no NSS. Use only the trusted, lockfile-pinned package archive.
  fs.mkdirSync(cache, { recursive: true });
  if (!fs.existsSync(path.join(cache, "lib/libnss3.so"))) {
    const archive = path.join(cache, "al2023.tar");
    const bundled = path.join(
      root,
      "mobile/preview/node_modules/@sparticuz/chromium/bin/al2023.tar.br",
    );
    fs.writeFileSync(
      archive,
      zlib.brotliDecompressSync(fs.readFileSync(bundled)),
    );
    execFileSync("tar", ["-xf", archive, "-C", cache]);
  }
  const unsafe = new Set([
    "--disable-web-security",
    "--allow-running-insecure-content",
    "--disable-site-isolation-trials",
    "--single-process",
    "--in-process-gpu",
  ]);
  return playwright.launch({
    executablePath: await chromium.executablePath(),
    headless: true,
    args: chromium.args.filter((x) => !unsafe.has(x)),
    env: {
      ...process.env,
      LD_LIBRARY_PATH: [path.join(cache, "lib"), process.env.LD_LIBRARY_PATH]
        .filter(Boolean)
        .join(":"),
    },
  });
}
