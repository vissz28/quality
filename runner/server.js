"use strict";

/**
 * Node.js test runner.
 *
 * A tiny HTTP service whose only job is to execute the Playwright TypeScript
 * that the Python service generates from the Gherkin scenarios, and hand back
 * the raw Playwright JSON report. The Python container has no Node.js, so it
 * POSTs the generated code here instead of shelling out to `npm`/`npx` itself.
 *
 *   POST /run   { "code": "<playwright .spec.ts source>" }
 *     -> 200    the raw Playwright JSON report (as produced by --reporter=json)
 *     -> 4xx/5xx { "execution_error": "..." }
 *
 *   GET  /health -> { "status": "ok" }
 *
 * @playwright/test is installed once at image-build time in WORKSPACE, so each
 * request only drops a spec file and runs it — no per-request npm install.
 */

const http = require("http");
const os = require("os");
const path = require("path");
const fs = require("fs/promises");
const crypto = require("crypto");
const { spawn } = require("child_process");

const PORT = Number(process.env.PORT || 3000);
// Directory where @playwright/test is installed (see Dockerfile). Tests run here.
const WORKSPACE = process.env.RUNNER_WORKSPACE || __dirname;
const TEST_TIMEOUT_MS = Number(process.env.RUNNER_TEST_TIMEOUT_MS || 300_000); // 5 min
const MAX_BODY_BYTES = 5 * 1024 * 1024; // 5 MB of generated code is plenty

const PLAYWRIGHT_CONFIG = `import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.',
  timeout: 30_000,
  retries: 0,
  reporter: 'json',
});
`;

function send(res, status, payload) {
  const body = typeof payload === "string" ? payload : JSON.stringify(payload);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

/**
 * Run one generated spec through Playwright and return { status, output }.
 * `output` is the raw stdout (the JSON report) which the caller passes through
 * untouched — parsing stays on the Python side.
 */
async function runPlaywright(code) {
  const id = crypto.randomBytes(6).toString("hex");
  const specName = `generated-${id}.spec.ts`;
  const specPath = path.join(WORKSPACE, specName);
  const configPath = path.join(WORKSPACE, "playwright.config.ts");

  await fs.writeFile(specPath, code, "utf8");
  // Config is idempotent; write it once per request to be safe.
  await fs.writeFile(configPath, PLAYWRIGHT_CONFIG, "utf8");

  try {
    return await new Promise((resolve) => {
      const proc = spawn(
        "npx",
        ["playwright", "test", specName, "--reporter=json"],
        { cwd: WORKSPACE, env: process.env }
      );

      let stdout = "";
      let stderr = "";
      let timedOut = false;

      const timer = setTimeout(() => {
        timedOut = true;
        proc.kill("SIGKILL");
      }, TEST_TIMEOUT_MS);

      proc.stdout.on("data", (d) => (stdout += d.toString()));
      proc.stderr.on("data", (d) => (stderr += d.toString()));

      proc.on("error", (err) => {
        clearTimeout(timer);
        resolve({
          ok: false,
          error:
            err.code === "ENOENT"
              ? "Playwright not found in runner image."
              : `Failed to start Playwright: ${err.message}`,
        });
      });

      proc.on("close", () => {
        clearTimeout(timer);
        if (timedOut) {
          resolve({ ok: false, error: "Test execution timed out." });
          return;
        }
        // Playwright exits non-zero when tests fail — that's expected and the
        // JSON report is still on stdout. Only treat a missing report as error.
        if (!stdout.includes("{")) {
          resolve({
            ok: false,
            error: `No JSON report produced. ${stderr.slice(0, 500)}`.trim(),
          });
          return;
        }
        resolve({ ok: true, output: stdout });
      });
    });
  } finally {
    await fs.rm(specPath, { force: true }).catch(() => {});
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    return send(res, 200, { status: "ok" });
  }

  if (req.method === "POST" && req.url === "/run") {
    let payload;
    try {
      const raw = await readBody(req);
      payload = JSON.parse(raw || "{}");
    } catch (err) {
      return send(res, 400, { execution_error: `Invalid request: ${err.message}` });
    }

    const code = payload && payload.code;
    if (typeof code !== "string" || !code.trim()) {
      return send(res, 400, { execution_error: "Missing 'code' in request body." });
    }

    try {
      const result = await runPlaywright(code);
      if (!result.ok) {
        return send(res, 200, { execution_error: result.error });
      }
      // Pass the raw Playwright JSON report straight through.
      return send(res, 200, result.output);
    } catch (err) {
      return send(res, 500, { execution_error: `Runner error: ${err.message}` });
    }
  }

  return send(res, 404, { execution_error: "Not found." });
});

server.listen(PORT, () => {
  console.log(`[runner] listening on :${PORT} (workspace: ${WORKSPACE})`);
});
