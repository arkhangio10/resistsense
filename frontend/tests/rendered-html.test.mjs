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
  assert.match(html, /Predict .* Challenge .* Abstain/);
  assert.match(html, /See resistance before confidence becomes risk/);
  assert.match(html, /Upload bacterial genome/);
  assert.match(html, /Supported bacterium/);
  assert.match(html, /Escherichia coli/);
  assert.match(html, /no-call/i);
  assert.match(html, /laboratory susceptibility testing/i);
  assert.match(html, /og-cinematic\.png/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i);
});

test("frontend delegates scientific decisions to the API", async () => {
  const [page, layout, packageJson, simulation] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../components/BioSimulation.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(page, /NEXT_PUBLIC_API_URL/);
  assert.match(page, /\/api\/v1\/analyze/);
  assert.match(page, /\/api\/v1\/prediction-autopsy/);
  assert.match(page, /\/api\/v1\/safety-report/);
  assert.match(page, /\/api\/v1\/evidence-audit/);
  assert.match(page, /\/api\/v1\/verified-demo/);
  assert.match(page, /\/api\/v1\/auditor-safety-eval/);
  assert.match(page, /\/api\/v1\/system-provenance/);
  assert.match(page, /Start 90-second judge tour/);
  assert.match(page, /Verified frozen-test case/);
  assert.match(page, /GPT-5\.6 Evidence Conflict Auditor/);
  assert.match(page, /See exactly what the firewall challenged/);
  assert.match(page, /Uncertainty becomes a worklist/);
  assert.match(page, /Guardrails are tested, not trusted/);
  assert.match(page, /Every result carries its receipts/);
  assert.match(page, /0 raw DNA bases sent/);
  assert.match(page, /Decision locked before the optional GPT audit/);
  assert.match(page, /Raw FASTA, original filename, checksum/);
  assert.match(page, /Download JSON/);
  assert.match(page, /Prediction autopsy/i);
  assert.match(page, /Residual error/);
  assert.match(page, /BioSimulation/);
  assert.match(page, /Run genomic assessment/);
  assert.match(page, /Antibiotic assessments/);
  assert.match(page, /type="file"/);
  assert.doesNotMatch(page, /Math\.random|mockProbability|fakeResult/i);
  assert.match(page, /Applying safety barriers/);
  assert.match(simulation, /prefers-reduced-motion/);
  assert.match(simulation, /fallback={<StaticSpecimen/);
  assert.match(simulation, /Peptidoglycan synthesis \/ PBPs/);
  assert.match(simulation, /DNA gyrase \/ topoisomerase IV/);
  assert.match(simulation, /30S ribosome \/ 16S rRNA/);
  assert.match(simulation, /Sequential folate synthesis/);
  assert.match(simulation, /ENVELOPE LYSED/);
  assert.match(simulation, /REPLICATION FAILURE/);
  assert.match(simulation, /MEMBRANE FAILURE/);
  assert.match(simulation, /GROWTH ARREST/);
  assert.match(simulation, /CELLULAR FUNCTION PRESERVED/);
  assert.match(simulation, /NO-CALL · NO RESPONSE INFERRED/);
  assert.match(simulation, /Mechanism-informed illustration/);
  assert.doesNotMatch(simulation, /organism viability is measured/i);
  assert.match(layout, /ResistSense \| Genome Firewall/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
