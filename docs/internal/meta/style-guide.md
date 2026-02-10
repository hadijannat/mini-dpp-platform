# Documentation Style Guide

## Naming

- File names must use `kebab-case.md`.
- Dated reports should use `topic-YYYY-MM-DD.md`.

## Required Structure

- Exactly one H1 per document.
- Internal docs should include YAML front matter:

```yaml
---
title: <document title>
owner: <team-or-person>
status: draft|active|archived
audience: internal
last_reviewed: YYYY-MM-DD
---
```

## Links and Assets

- Use relative links within the repository.
- Do not reference legacy paths that were moved.
- Image links should point to `docs/public/assets/**`.

## Quality Gates

- `markdownlint-cli2` must pass.
- `lychee` link checks must pass for Markdown files.
