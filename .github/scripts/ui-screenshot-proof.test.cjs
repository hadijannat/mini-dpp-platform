const test = require("node:test");
const assert = require("node:assert/strict");

const {
  evaluateScreenshotProof,
  hasScreenshotEvidence,
  isUiFile,
} = require("./ui-screenshot-proof.cjs");

test("isUiFile matches prefixed frontend source paths", () => {
  assert.equal(isUiFile("frontend/src/components/Button.tsx"), true);
  assert.equal(isUiFile("frontend/public/logo.svg"), true);
});

test("isUiFile matches frontend suffix fallback", () => {
  assert.equal(isUiFile("frontend/docs/sample.html"), true);
  assert.equal(isUiFile("frontend/styles/app.scss"), true);
  assert.equal(isUiFile("backend/app/main.py"), false);
});

test("hasScreenshotEvidence detects markdown image", () => {
  const body = "## Notes\n![UI](https://example.com/ui.png)";
  assert.equal(hasScreenshotEvidence(body), true);
});

test("hasScreenshotEvidence detects non-empty screenshots line", () => {
  const body = "- Screenshots (if UI changes): https://example.com/snap.png";
  assert.equal(hasScreenshotEvidence(body), true);
});

test("hasScreenshotEvidence rejects empty screenshots line variants", () => {
  assert.equal(hasScreenshotEvidence("- Screenshots (if UI changes): n/a"), false);
  assert.equal(hasScreenshotEvidence("- Screenshots (if UI changes): -"), false);
});

test("evaluateScreenshotProof passes when no UI files changed", () => {
  const result = evaluateScreenshotProof({
    files: [{ filename: "backend/app/main.py" }],
    body: "",
  });

  assert.equal(result.pass, true);
  assert.equal(result.uiChanged, false);
});

test("evaluateScreenshotProof fails when UI changed without evidence", () => {
  const result = evaluateScreenshotProof({
    files: [{ filename: "frontend/src/App.tsx" }],
    body: "- Screenshots (if UI changes): n/a",
  });

  assert.equal(result.uiChanged, true);
  assert.equal(result.pass, false);
});

test("evaluateScreenshotProof passes when UI changed with evidence", () => {
  const result = evaluateScreenshotProof({
    files: [{ filename: "frontend/src/App.tsx" }],
    body: "![ui](https://example.com/new-ui.png)",
  });

  assert.equal(result.uiChanged, true);
  assert.equal(result.pass, true);
});
