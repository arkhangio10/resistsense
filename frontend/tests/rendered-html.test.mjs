import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the ResistSense product shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>ResistSense \| Genome Firewall<\/title>/i);
  assert.match(html, /Predict · Challenge · Abstain/);
  assert.match(html, /Analizar un FASTA/);
  assert.match(html, /No-call/);
  assert.match(html, /pruebas de laboratorio/i);
  assert.match(html, /og\.png/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i);
});

test("frontend delegates scientific decisions to the API", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /NEXT_PUBLIC_API_URL/);
  assert.match(page, /\/api\/v1\/analyze/);
  assert.match(page, /\/api\/v1\/prediction-autopsy/);
  assert.match(page, /Prediction Autopsy/);
  assert.match(page, /Error residual/);
  assert.match(page, /type="file"/);
  assert.doesNotMatch(page, /Math\.random|mockProbability|fakeResult/i);
  assert.match(layout, /ResistSense \| Genome Firewall/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
