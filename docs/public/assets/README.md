# Documentation Assets

Static assets used by Markdown documentation.

## Directory Layout

- `images/`: UI captures and focused screenshots
- `storyboard/`: ordered step-by-step walkthrough frames

## Current Usage

- Root docs hub (`README.md`) links to public docs and does not embed long storyboard sequences.
- Full walkthrough image sequences are now documented in:
  - `docs/public/getting-started/README.md`
- Additional feature screenshots are referenced by public docs pages under `docs/public/**`.

## Maintenance Notes

- Reuse existing assets when possible; avoid duplicate images with different names.
- Keep references relative so markdown lint and link checks remain stable.
- Store only documentation assets here (no generated runtime artifacts).
