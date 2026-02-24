const DEFAULT_UI_PREFIXES = ["frontend/src/", "frontend/public/"];
const DEFAULT_UI_SUFFIXES = [
  ".tsx",
  ".jsx",
  ".css",
  ".scss",
  ".sass",
  ".less",
  ".html",
  ".svg",
];

const EMPTY_SCREENSHOT_VALUES = new Set(["", "-", "none", "n/a", "na", "not applicable"]);

function isUiFile(path, uiPrefixes = DEFAULT_UI_PREFIXES, uiSuffixes = DEFAULT_UI_SUFFIXES) {
  const filePath = String(path || "").trim();
  if (!filePath) {
    return false;
  }

  if (uiPrefixes.some((prefix) => filePath.startsWith(prefix))) {
    return true;
  }

  if (filePath.startsWith("frontend/") && uiSuffixes.some((suffix) => filePath.endsWith(suffix))) {
    return true;
  }

  return false;
}

function hasMarkdownImage(body) {
  return /!\[[^\]]*]\([^)]+\)/m.test(String(body || ""));
}

function hasScreenshotLineEvidence(body) {
  const match = String(body || "").match(/^- Screenshots \(if UI changes\):\s*(.+)$/im);
  if (!match) {
    return false;
  }

  const value = match[1].trim().toLowerCase();
  return !EMPTY_SCREENSHOT_VALUES.has(value);
}

function hasScreenshotEvidence(body) {
  return hasMarkdownImage(body) || hasScreenshotLineEvidence(body);
}

function evaluateScreenshotProof({ files, body, uiPrefixes, uiSuffixes }) {
  const normalizedFiles = Array.isArray(files) ? files : [];
  const changedUi = normalizedFiles.some((file) => {
    const filename = typeof file === "string" ? file : file?.filename || file?.path || "";
    return isUiFile(filename, uiPrefixes, uiSuffixes);
  });

  if (!changedUi) {
    return {
      uiChanged: false,
      hasEvidence: true,
      pass: true,
      reason: "No UI changes detected.",
    };
  }

  const hasEvidence = hasScreenshotEvidence(body);
  return {
    uiChanged: true,
    hasEvidence,
    pass: hasEvidence,
    reason: hasEvidence
      ? "Screenshot proof found for UI changes."
      : "UI changes detected but PR body does not include screenshot evidence.",
  };
}

module.exports = {
  DEFAULT_UI_PREFIXES,
  DEFAULT_UI_SUFFIXES,
  EMPTY_SCREENSHOT_VALUES,
  evaluateScreenshotProof,
  hasMarkdownImage,
  hasScreenshotEvidence,
  hasScreenshotLineEvidence,
  isUiFile,
};
