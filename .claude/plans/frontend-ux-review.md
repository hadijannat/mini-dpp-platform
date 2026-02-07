# Frontend & UX Review -- Phase 1 Findings Report

## Executive Summary

Reviewed all frontend source files in `frontend/src/`, `frontend/tests/`, and configuration files. The application uses React 18, TanStack Query, React Hook Form, shadcn/ui (Radix), and TailwindCSS. The codebase is well-structured with consistent error handling patterns, but has significant gaps in accessibility, test coverage, code splitting, and viewer production-readiness. Below are the top 10 findings ranked by severity.

---

## Finding 1: Public DPP Viewer Requires Authentication (P0 -- Critical)

**Description:** The public DPP viewer (the page QR code consumers land on after scanning) is wrapped in `<ProtectedRoute>`, requiring OIDC authentication. A consumer scanning a QR code on a product is redirected to Keycloak login, which defeats the purpose of a public Digital Product Passport.

**Evidence:**
- `frontend/src/App.tsx:46-57` -- Viewer routes `/dpp/:dppId`, `/p/:slug`, `/t/:tenantSlug/dpp/:dppId`, `/t/:tenantSlug/p/:slug` are all wrapped in `<ProtectedRoute>` with no exemption.
- `frontend/src/auth/ProtectedRoute.tsx:14-19` -- Unauthenticated users are redirected to `/login`.

**Risk:** QR code scans by consumers, regulators, customs, and recyclers will fail unless they have a Keycloak account. This blocks the core use case of EU ESPR DPP compliance: any person scanning the product should be able to view the passport.

**Fix Plan:**
1. Make viewer routes public (remove `ProtectedRoute` wrapper for viewer routes).
2. Update `DPPViewerPage` to optionally pass token (use it if available, fetch without auth if not).
3. Backend needs a corresponding public endpoint (or the existing one needs to allow anonymous access for published DPPs).
4. Add a `ViewerLayout` header link to "Sign in" for publishers who want to access the console.

**Acceptance Criteria:**
- Unauthenticated user can access `/dpp/:id` and `/p/:slug` and see the full DPP.
- Published DPPs are viewable without login; draft DPPs still require auth.

**Test Plan:**
- E2E test: visit a published DPP URL in incognito (no session); verify content loads without redirect.
- E2E test: visit a draft DPP URL without auth; verify appropriate error or redirect.

---

## Finding 2: No Lazy Loading / Code Splitting (P1 -- High)

**Description:** All 15+ page components are eagerly imported in `App.tsx` with static `import` statements. There is zero usage of `React.lazy()` or dynamic `import()` anywhere in the frontend. This means the entire application (editor, viewer, admin, connectors, masters, data carriers, all field components) is loaded as a single bundle.

**Evidence:**
- `frontend/src/App.tsx:5-21` -- All pages are statically imported at the top level.
- Grep for `React.lazy|import()|Suspense` across `frontend/src/` returned zero results.
- The editor alone includes 12+ field components, Zod schema builder, form defaults, validation utils, concept descriptions hook, etc. -- all loaded even for viewer-only users.

**Risk:** Large initial bundle size hurts Time-to-First-Paint, especially for QR code consumers on mobile devices. The editor feature module (~20+ files) is loaded even when viewing a DPP.

**Fix Plan:**
1. Wrap each route's page component with `React.lazy()` and `<Suspense fallback={<LoadingSpinner />}>`.
2. At minimum, split: viewer pages, editor pages (heaviest), admin pages, connectors page, masters page.
3. Consider a per-feature dynamic import pattern: `const DPPViewerPage = lazy(() => import('./features/viewer/pages/DPPViewerPage'))`.

**Acceptance Criteria:**
- `npm run build` produces multiple chunks (viewer, editor, admin, etc.).
- Network tab shows only viewer chunk loaded when accessing `/dpp/:id`.

**Test Plan:**
- Build the app and verify Vite output shows multiple chunks.
- Lighthouse audit to confirm improved LCP/FCP.

---

## Finding 3: Minimal Accessibility (a11y) -- No ARIA, No Focus Management, No Skip Links (P1 -- High)

**Description:** The application has almost no accessibility support beyond what Radix UI primitives provide by default. Custom components lack ARIA attributes, keyboard navigation, focus trapping, skip-to-content links, and screen reader announcements.

**Evidence:**
- Grep for `aria-|role=` found only 11 total occurrences, all inside shadcn/ui primitives (`table.tsx`, `breadcrumb.tsx`, `alert.tsx`). Zero custom ARIA attributes in application code.
- Grep for `tabIndex|onKeyDown` found exactly 1 occurrence (`MultiLangField.tsx:87`).
- `frontend/src/App.tsx:33-36` -- Loading spinner has no `aria-label` or `role="status"`.
- `frontend/src/components/loading-spinner.tsx` -- No `aria-busy`, `aria-label`, or `role="status"` on loading states.
- `frontend/src/features/publisher/pages/DashboardPage.tsx:165-170` -- Dashboard table rows are clickable via `onClick` but have no `role="link"`, no `tabIndex`, no keyboard handler.
- `frontend/src/app/layouts/PublisherLayout.tsx:141-148` -- Sidebar collapse button has no `aria-label`.
- `frontend/src/features/editor/components/fields/PropertyField.tsx:77-91` -- Form inputs use plain `<input>` without `id` + `<label htmlFor>` association.

**Risk:** Non-compliance with WCAG 2.1 AA. Unusable for screen reader users. Keyboard-only users cannot navigate the sidebar, tables, or forms. May violate EU accessibility regulations for public-facing DPP viewer.

**Fix Plan:**
1. Add skip-to-content link in both layouts.
2. Add `role="status"` and `aria-label="Loading"` to LoadingSpinner.
3. Link form labels to inputs via `id`/`htmlFor` in FieldWrapper.
4. Add `aria-label` to sidebar collapse toggle.
5. Make dashboard table rows keyboard-navigable (`tabIndex={0}`, `onKeyDown` Enter handler, `role="link"`).
6. Add `aria-current="page"` to active nav items in SidebarNav.
7. Test with screen reader (VoiceOver/NVDA).

**Acceptance Criteria:**
- All interactive elements are keyboard-accessible.
- Screen reader can navigate and announce all major components.
- Lighthouse Accessibility score >= 90.

**Test Plan:**
- Automated: `axe-core` integration in Vitest for component tests.
- Manual: VoiceOver walkthrough of viewer and editor flows.

---

## Finding 4: E2E Test Coverage is Minimal -- Single Spec File (P1 -- High)

**Description:** There is exactly one E2E test file (`tests/e2e/navigation.spec.ts`) with one test case. It covers publisher navigation flow only. Large functional areas are completely untested.

**Evidence:**
- `frontend/tests/e2e/navigation.spec.ts` -- Single file, single test case (`publisher navigation and action buttons work`).
- No E2E coverage for: DPP viewer page, connectors page, admin/tenants page, form editor (field editing, validation, save), export/download, data carriers/QR generation, mobile viewport, error states.
- Playwright config (`frontend/playwright.config.ts`) only tests with Chromium, no multi-browser coverage.

**Risk:** Regressions in viewer, editor, admin, and connectors flows will go undetected. Critical user paths (editing a submodel, publishing, exporting) have zero automated coverage.

**Fix Plan:**
1. Add E2E specs for: viewer flow (public DPP view), submodel editing (fill fields, save), publish flow, export (JSON/AASX), connectors CRUD, tenants CRUD, data carriers QR generation.
2. Add mobile viewport test (Playwright `viewport` config).
3. Add Playwright projects for Firefox and WebKit.
4. Consider Page Object Model pattern for maintainability.

**Acceptance Criteria:**
- At least 6 E2E spec files covering major user flows.
- Tests pass in CI with Chromium.

**Test Plan:**
- Each new spec file should be self-contained and idempotent.
- CI pipeline runs all E2E tests on each PR.

---

## Finding 5: Viewer Not Optimized for QR Scan Consumers -- Missing SEO, Meta, Mobile UX (P1 -- High)

**Description:** The DPP viewer page (the consumer-facing page reached via QR scan) lacks production-readiness features for its primary audience: mobile users scanning a QR code.

**Evidence:**
- `frontend/index.html` -- No `<meta name="description">`, no Open Graph tags, no structured data (JSON-LD). Title is generic "Mini DPP Platform".
- No `<meta name="theme-color">` for mobile browser chrome.
- No service worker or offline fallback -- if a user scans a QR code with poor connectivity, they get nothing.
- `frontend/src/features/viewer/pages/DPPViewerPage.tsx` -- No `document.title` update for the product being viewed.
- `frontend/src/features/viewer/components/ESPRTabs.tsx:16-28` -- Tab labels are hidden on mobile (`hidden sm:inline`), but no `aria-label` alternative is provided, so mobile users see only icons with badge counts.
- No print stylesheet for regulators who may want to print the passport.
- No share button (Web Share API) for mobile users to share the DPP link.

**Risk:** Poor first impression for the primary target audience (QR code scanners). No SEO indexing for published DPPs. No offline resilience for factory/warehouse environments.

**Fix Plan:**
1. Add dynamic `<title>` and `<meta description>` per DPP using `useEffect` + `document.title`.
2. Add `aria-label` to tab triggers for mobile (when text is hidden).
3. Add `<meta name="theme-color">` to `index.html`.
4. Consider adding a basic service worker for offline caching of viewed DPPs (PWA lite).
5. Add a share button using the Web Share API with fallback copy-to-clipboard.
6. Add print-friendly CSS (`@media print`).

**Acceptance Criteria:**
- Viewer page updates document title to product name.
- ESPR tabs are usable on mobile (labels or aria-labels visible).
- Share button works on mobile.

**Test Plan:**
- E2E test: verify document title changes on viewer page.
- Manual: test on mobile Safari/Chrome via responsive mode.

---

## Finding 6: Tenant Switcher UX Issues -- Full Page Reload, No Validation (P2 -- Medium)

**Description:** The tenant selector component has several UX issues: it triggers a full page reload on change, has no confirmation dialog, and uses hardcoded gray color classes instead of semantic tokens.

**Evidence:**
- `frontend/src/app/components/TenantSelector.tsx:61` -- `window.location.reload()` on tenant change, losing all in-memory state and TanStack Query cache.
- `frontend/src/app/components/TenantSelector.tsx:66-71` -- Uses `text-gray-400`, `bg-gray-800`, `text-gray-100`, `border-gray-700` -- hardcoded colors instead of semantic tokens.
- `frontend/src/app/components/TenantSelector.tsx:80-86` -- Fallback text input for tenant slug with no validation; user can type invalid slug.
- `frontend/src/lib/tenant.ts:20-28` -- `useTenantSlug` uses local component state + localStorage, not a React context. Multiple components reading tenant slug will not stay in sync until page reload.
- No handling of "user has zero tenants" edge case -- shows an empty text input.

**Risk:** Jarring UX on tenant switch (full reload). Possible data inconsistency if tenant slug is changed mid-operation. Invalid tenant slugs can be entered without feedback.

**Fix Plan:**
1. Replace `window.location.reload()` with TanStack Query cache invalidation (`queryClient.clear()`) + programmatic navigation.
2. Wrap tenant slug in a React context so all components react to changes.
3. Replace hardcoded gray colors with sidebar semantic tokens.
4. Add validation on the fallback text input (alphanumeric + hyphens only).
5. Show a "No tenants available" message with action to contact admin.

**Acceptance Criteria:**
- Tenant switch does not cause full page reload.
- Invalid tenant slugs are rejected with inline error.
- Semantic tokens used for all colors.

**Test Plan:**
- Unit test: `useTenantSlug` hook with context.
- E2E test: switch tenant and verify no full reload.

---

## Finding 7: CSP Header Includes Dev-Only Domains in Production Config (P2 -- Medium)

**Description:** The nginx CSP `connect-src` directive includes `http://localhost:*`, `https://*.keycloak.local`, and `https://*.example.com`, which are development remnants that widen the attack surface in production.

**Evidence:**
- `frontend/nginx.conf:13` -- `connect-src 'self' http://localhost:* https://*.dpp-platform.dev https://*.keycloak.local https://*.example.com`
- `frontend/nginx.conf:29` -- Same CSP repeated in static assets location block.

**Risk:** Overly broad CSP in production allows XHR/fetch to `*.example.com` and `*.keycloak.local`, which is unnecessary and widens attack surface. The `http://localhost:*` entry indicates the CSP is not environment-aware.

**Fix Plan:**
1. Make CSP environment-aware: use Docker build args or envsubst to template the CSP for dev vs. production.
2. Production CSP should be: `connect-src 'self' https://*.dpp-platform.dev`.
3. Remove `*.keycloak.local` and `*.example.com` from production CSP.
4. Consider adding `upgrade-insecure-requests` directive for production.

**Acceptance Criteria:**
- Production nginx.conf has a tightened CSP without dev domains.
- Dev compose override or env variable allows broader CSP locally.

**Test Plan:**
- Verify CSP header in browser DevTools on production.
- Verify OIDC login still works with tightened CSP.

---

## Finding 8: Form Editor Inputs Not Using shadcn/ui Components -- Consistency Gap (P2 -- Medium)

**Description:** The editor field components use plain HTML `<input>`, `<select>`, and `<button>` elements instead of shadcn/ui primitives (`Input`, `Select`, `Button`). This causes visual inconsistency and accessibility gaps compared to the rest of the application.

**Evidence:**
- `frontend/src/features/editor/components/fields/PropertyField.tsx:77-91` -- Uses plain `<input>` with manual Tailwind classes instead of `<Input>` from `@/components/ui/input`.
- `frontend/src/features/editor/components/fields/ListField.tsx:64-73` -- Add/Remove buttons use plain `<button>` instead of `<Button>`.
- `frontend/src/features/editor/components/FieldWrapper.tsx:23-29` -- Label is a shadcn `<Label>` but no `htmlFor` is set, so it is not semantically linked to the input.
- `frontend/src/features/publisher/pages/DataCarriersPage.tsx:258-269` -- Uses plain `<select>` instead of `<Select>`.
- `frontend/src/features/publisher/pages/MastersPage.tsx:703-715` -- Uses plain `<select>` for variable type.
- `frontend/src/features/admin/pages/TenantsPage.tsx:249-257` -- Uses plain `<select>` for role.

**Risk:** Inconsistent keyboard behavior, focus ring styling, and screen reader behavior between editor fields and the rest of the app. Plain `<select>` elements do not match the visual design system.

**Fix Plan:**
1. Replace plain `<input>` in PropertyField (and other field components) with shadcn `<Input>`.
2. Replace plain `<select>` in DataCarriersPage, MastersPage, TenantsPage with shadcn `<Select>`.
3. Replace plain `<button>` in ListField with shadcn `<Button>`.
4. Pass `id` to input elements and `htmlFor` to `<Label>` in FieldWrapper via a generated ID.

**Acceptance Criteria:**
- All form inputs use shadcn/ui primitives.
- Labels are semantically linked to inputs.

**Test Plan:**
- Visual regression testing.
- Keyboard navigation test for form fields.

---

## Finding 9: DPP Viewer Data Rendering -- Content Injection Risk (P2 -- Medium)

**Description:** The DPP viewer renders user-controlled field values from the AAS environment directly into the DOM. While React auto-escapes text content (preventing script injection), certain areas render data that could be misleading. The `formUrl` field in the editor FieldWrapper renders an anchor tag where the URL comes from server template definitions.

**Evidence:**
- `frontend/src/features/viewer/components/DataField.tsx:28-30` -- Renders string values directly (safe due to React escaping).
- `frontend/src/features/viewer/components/DPPHeader.tsx:31` -- Renders `String(value)` for asset IDs.
- `frontend/src/features/viewer/components/RawSubmodelTree.tsx:17` -- Renders `submodel.idShort` and `submodel.id` as text.
- `frontend/src/features/editor/components/FieldWrapper.tsx:43-50` -- Renders `<a href={formUrl}>` -- while `formUrl` comes from server-side template definitions (trusted), the href is not validated.
- No `dangerouslySetInnerHTML` usage confirmed via grep (good).

**Risk:** Low direct XSS risk due to React auto-escaping. Primary concern is content injection: a malicious DPP could include misleading field names or values. The `formUrl` link renders whatever URL the server provides without client-side validation.

**Fix Plan:**
1. Add URL validation for `formUrl` (ensure it starts with `https://` or is a relative path).
2. Consider adding a visual indicator for "user-provided data" in the viewer.
3. Add `rel="noopener noreferrer"` to the `formUrl` link (currently only has `rel="noreferrer"`).
4. Truncate extremely long field values in the viewer to prevent UI breakage.

**Acceptance Criteria:**
- `formUrl` only renders for `https://` URLs or relative paths.
- Long field values are truncated with expansion option.

**Test Plan:**
- Unit test: DataField with extremely long strings, HTML-like strings, URLs.
- Unit test: FieldWrapper with various formUrl values.

---

## Finding 10: No Internationalization (i18n) Infrastructure (P2 -- Medium)

**Description:** All UI strings are hardcoded in English throughout the application. There is no i18n library, no translation files, no locale detection, and no mechanism for localization. While the AAS data model supports `MultiLanguageProperty` for data fields, the UI chrome itself is English-only.

**Evidence:**
- Grep across entire `frontend/src/` for `t(`, `useTranslation`, `i18n`, `intl`, `FormattedMessage` returned zero results.
- `frontend/package.json` -- No i18n dependency.
- All button labels, page titles, error messages, and descriptions are hardcoded English strings throughout all components.
- Date formatting uses `toLocaleDateString()` (which does respect browser locale), but labels around dates are English.

**Risk:** The EU ESPR regulation may require DPP information to be available in multiple EU languages. The UI wrapper (headers, tabs, buttons, error messages) is English-only. This may limit adoption in non-English EU markets.

**Fix Plan:**
1. Add `react-i18next` as a dependency.
2. Extract all UI strings into a `locales/en.json` file.
3. Wrap string references with `t()` function.
4. Add language detection from browser locale.
5. Start with English + one additional language (e.g., German) as proof of concept.
6. This is a large effort -- should be a separate workstream.

**Acceptance Criteria:**
- All UI strings extracted to translation files.
- Language switcher in viewer layout.
- At least English + one other language.

**Test Plan:**
- Unit test: verify translation keys resolve correctly.
- Visual test: verify layout does not break with longer German strings.

---

## Effort Estimates

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| 1 | Viewer requires auth | P0 | 4-8 hours (frontend + backend) |
| 2 | No code splitting | P1 | 2-4 hours |
| 3 | Accessibility gaps | P1 | 8-16 hours (incremental) |
| 4 | E2E test gaps | P1 | 16-24 hours (6+ specs) |
| 5 | Viewer mobile/SEO | P1 | 8-12 hours |
| 6 | Tenant switcher UX | P2 | 4-6 hours |
| 7 | CSP hardening | P2 | 2-3 hours |
| 8 | Editor input consistency | P2 | 4-6 hours |
| 9 | Viewer data rendering | P2 | 2-3 hours |
| 10 | i18n infrastructure | P2 | 16-24 hours (foundation) |

**Total estimated effort: 66-106 hours**

Priority order for immediate action: Finding 1 (P0) > Finding 2 > Finding 3 > Finding 5 > Finding 4 (P1s).
