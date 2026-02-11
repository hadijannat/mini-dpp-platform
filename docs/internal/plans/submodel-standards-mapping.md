# Submodel Standards And Regulatory Mapping (v1)

## Purpose
This document maps submodel UX and architecture requirements to AAS/IDTA, ESPR, battery-passport timelines, and accessibility standards.

This is a product/engineering implementation mapping, not legal advice.

## Source Baseline (official / primary)

1. Regulation (EU) 2024/1781 (ESPR): https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng
2. Regulation (EU) 2023/1542 (Batteries): https://eur-lex.europa.eu/eli/reg/2023/1542/oj/eng
3. European Commission ESPR page: https://environment.ec.europa.eu/publications/ecodesign-sustainable-products-regulation_en
4. EC Press release (Working Plan 2025-2030): https://ec.europa.eu/commission/presscorner/detail/en/ip_25_1081
5. JRC DPP next-steps page (provided baseline URL): https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/next-steps-towards-regulation-digital-product-passports-2024-04-17_en
6. JRC standards communication (provided baseline URL): https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/standards-enhancing-product-sustainability-2026-01-07_en
7. IDTA AAS specifications hub: https://industrialdigitaltwin.org/en/content-hub/details/asset-administration-shell-specifications
8. IDTA Submodel templates repo: https://github.com/admin-shell-io/submodel-templates
9. IDTA Digital Nameplate template README (provided baseline URL): https://raw.githubusercontent.com/admin-shell-io/submodel-templates/main/published/Digital%20nameplate/README.md
10. IDTA Carbon Footprint template README (provided baseline URL): https://raw.githubusercontent.com/admin-shell-io/submodel-templates/main/published/Carbon%20Footprint/README.md
11. WCAG 2.2: https://www.w3.org/TR/WCAG22/
12. WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/patterns/
13. EC Green Forum summary (ESPR in-force date + Working Plan adoption date): https://green-forum.ec.europa.eu/green-business/ecodesign-sustainable-products-regulation_en
14. EC Batteries Regulation implementation page: https://environment.ec.europa.eu/topics/waste-and-recycling/batteries-and-accumulators/implementation-batteries-regulation_en
15. Consilium adoption summary (battery passport/QR trajectory): https://www.consilium.europa.eu/en/press/press-releases/2023/07/10/council-adopts-new-regulation-on-batteries-and-waste-batteries/
16. EC delegated-act page (staged batteries implementation checkpoints incl. 2025 milestones): https://environment.ec.europa.eu/topics/waste-and-recycling/batteries-and-accumulators/adopted-delegated-act-methodology-and-targets-recycling-efficiency-and-material-recovery_en

## Date Anchors Used In Product Planning

1. **ESPR entered into force on 18 July 2024** (EC Green Forum / Commission context pages).
2. **Ecodesign Working Plan 2025-2030 was adopted on 16 April 2025** (EC Green Forum / Commission context pages).
3. **Battery Regulation entered into force in 2023 and is implemented in stages from 2024 onward** (EC batteries implementation page).
4. **Roadmap checkpoint: 2025 delegated/implementing-act milestones** are explicitly tracked in EC batteries implementation materials, including **31 December 2025** target milestones in delegated-act context.
5. **Battery passport/QR applicability trajectory is framed around 2027** in official EU communications (Consilium adoption communication and regulation-driven implementation schedule).
6. **Accessibility baseline is WCAG 2.2 + WAI-ARIA APG** for all three surfaces (publisher, editor, viewer).

## Architecture Mapping Matrix

| Domain | Normative anchor | Product requirement | Mapped implementation control |
|---|---|---|---|
| AAS/IDTA submodel fidelity | IDTA AAS specifications hub + IDTA templates repository | Bind submodels by semantic contract, not string heuristics | Backend `submodel_binding.py` resolver + `submodel_bindings` in DPP detail responses |
| AAS update determinism | AAS/IDTA contract expectations for revisioned submodels | Avoid ambiguous template-target updates | `PUT /dpps/{id}/submodel` supports `submodel_id`; backend returns 409 on ambiguous binding conflicts |
| Template refresh governance | IDTA template provenance and versioning model | Deterministic refresh/rebuild outcomes | `POST /dpps/{id}/submodels/refresh-rebuild` returns `{attempted,succeeded,failed,skipped}` |
| ESPR category-oriented communication | ESPR regulation + Working Plan policy direction | Surface sustainability-relevant content in digestible categories | Viewer category tabs classify deep submodel nodes; publisher summary cards expose completion/risk cues |
| Battery-passport readiness | Batteries Regulation + EU timeline communications | Keep architecture battery-passport ready while upstream templates may lag | Registry keeps `battery-passport` in semantic map with explicit support flags (`support_status`, `refresh_enabled`) |
| Horizontal sustainability standardization | JRC Jan 2026 communication (provided baseline source) | Preserve semantic/provenance metadata to support cross-standard traceability | Deep tree renderer includes semantic IDs and provenance-facing metadata toggles |
| Accessibility conformance | WCAG 2.2 + WAI-ARIA APG | Keyboard, semantics, error handling, async announcements | Tab/accordion/collapsible semantics, aria-live save announcements, non-color error messaging, min target-size design intent |

## ESPR And Battery Rules To Encode In UX/Product Logic (v1)

### A) ESPR core obligations context
1. Treat product-group rollout as delegated-act-driven.
2. Keep data model modular by submodel template and semantic ID.
3. Maintain explicit provenance/version metadata per template revision and rebuild run.

### B) Battery timeline handling
1. Keep battery passport templates and semantic aliases in registry now, even when not selectable.
2. Support quick activation path via `support_status` + `refresh_enabled` flips.
3. Preserve regulatory timeline messaging in roadmap as staged (2025 delegated/implementing-act checkpoints and 2027 applicability window).

## Accessibility Mapping (Non-negotiable)

| WCAG/WAI-ARIA baseline | Required behavior in this redesign |
|---|---|
| Perceivable + understandable errors | Top-level error summaries and field-linked messages in editor save flows |
| Operable keyboard patterns | Tabs, accordion/collapsible, tree expansion patterns follow APG interaction expectations |
| Programmatic naming | Every actionable control must have discernible text/label |
| Async state announcement | `saving`, `rebuilding`, and partial-failure outcomes announced via `aria-live` regions |
| Non-color-only semantics | Required/invalid/read-only states include textual/iconic cues, not color alone |

## Standards-to-Test Coverage Mapping

1. **Binding determinism**: backend unit tests for semantic exact/alias/idShort fallback binding and ambiguity handling.
2. **Nested structure rendering**: viewer and publisher use normalized deep tree model; category classification validates deep leaf extraction.
3. **Qualifier enforcement**: editor validation chain enforces required languages, ranges, regex, either-or groups, read-only, idShort naming constraints.
4. **Action policy consistency**: centralized `actionPolicy` drives primary button enablement against access+status.

## Source Retrieval Notes (2026-02-11)

1. Commission ESPR page, WCAG 2.2, and WAI-ARIA APG were directly retrievable and used as authoritative anchors.
2. Some provided URLs (notably certain JRC pages and press-corner deep pages) are intermittently rate-limited or unavailable from automated retrieval; links are retained as official baseline references for manual legal/policy verification.
3. Battery delegated/implementing-act scheduling details are treated as regulatory watchpoints and should be revalidated against EUR-Lex consolidated text and Commission delegated-act publications before legal-signoff milestones.
