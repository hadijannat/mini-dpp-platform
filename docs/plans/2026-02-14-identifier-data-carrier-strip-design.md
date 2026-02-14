# Design: Identifier & Data Carrier Strip

**Date**: 2026-02-14
**Status**: Approved
**PR**: TBD (follows PR #104)

## Context

DPP4.0 requires three layers alongside the AAS submodel templates: unique product identification, physical data carriers, and resolution protocols. The current `DppCompactModel` on the landing page shows only the AAS arch with 7 submodel cards. This design adds a visual layer above the arch showing the full identification and data carrier lifecycle.

## Decision

Add a **three-column horizontal strip** between the h2/toggle header and the AAS arch in `DppCompactModel`. The strip is always visible (not audience-toggle dependent) and shows:

1. **Unique Identifier** — Identity levels (Model/Batch/Item) and identifier schemes (GS1 GTIN, IEC 61406, Direct URL)
2. **Data Carrier** — Carrier types (QR Code, DataMatrix, NFC) and lifecycle states (Active, Deprecated, Withdrawn)
3. **Resolution** — Protocols (GS1 Digital Link, RFC 9264 Linkset) and URI pattern example

## Layout

```
┌─ UNIQUE IDENTIFIER ─┐ ┌─ DATA CARRIER ──┐ ┌─ RESOLUTION ──────┐
│  Identity Levels:    │ │  Carrier Types:  │ │  Protocols:        │
│  Model · Batch · Item│ │  QR · DataMatrix │ │  GS1 Digital Link  │
│                      │ │  · NFC           │ │  RFC 9264 Linkset  │
│  Schemes:            │ │                  │ │                    │
│  GS1 GTIN            │ │  Lifecycle:      │ │  URI Pattern:      │
│  IEC 61406           │ │  Active →        │ │  /01/{gtin}/       │
│  Direct URL          │ │  Deprecated →    │ │  21/{serial}       │
│                      │ │  Withdrawn       │ │                    │
└──────────────────────┘ └──────────────────┘ └────────────────────┘
```

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/features/landing/components/DppCompactModel.tsx` | Add 3-column strip between header and AAS arch |
| `frontend/src/styles/globals.css` | Add `.landing-id-layer` container class if needed |

## Design Decisions

- **Always visible**: Not behind the General/Implementer toggle since identification is structural
- **Color coding**: Identifier and Resolution use cyan top-border (core protocol), Carrier uses amber (physical artifact)
- **Icons**: Lucide icons (Fingerprint, QrCode, Link2) for column headers
- **Responsive**: `grid-cols-3` at md+, stacks to single column on mobile
- **Static content**: Inline constants, not from dppModelContent.ts (structural, not per-submodel)
- **Height**: Adds ~150px to component (total ~670px from ~520px)

## Data Source (from codebase)

- Identity levels: `DataCarrierIdentityLevel` enum (MODEL, BATCH, ITEM)
- Identifier schemes: `DataCarrierIdentifierScheme` enum (GS1_GTIN, IEC61406, DIRECT_URL)
- Carrier types: `DataCarrierType` enum (QR, DATAMATRIX, NFC)
- Carrier lifecycle: `DataCarrierStatus` enum (ACTIVE, DEPRECATED, WITHDRAWN)
- Resolver: GS1 Digital Link (RFC 9264), IEC 61406 identification link
- URI pattern: `/01/{gtin}/21/{serial}` (GS1 AI syntax)
