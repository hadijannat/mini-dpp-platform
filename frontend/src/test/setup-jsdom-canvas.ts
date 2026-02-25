const isJsdomRuntime =
  typeof navigator !== 'undefined' && navigator.userAgent.toLowerCase().includes('jsdom');

if (isJsdomRuntime && typeof HTMLCanvasElement !== 'undefined') {
  // Keep existing behavior (null context) while preventing jsdom's noisy "not implemented" warning.
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    value: () => null,
  });
}
