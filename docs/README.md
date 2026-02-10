# Documentation Hub

This repository uses a centralized documentation model.

## Structure

- `docs/public/`: Public-facing product and operator documentation.
- `docs/internal/`: Internal audits, plans, reviews, and evidence artifacts.

## Contributing

1. Place new docs under `docs/public/` or `docs/internal/`.
2. Use `kebab-case.md` file names.
3. Keep links relative and update links when files move.
4. Run docs checks before pushing:
   - `markdownlint-cli2 'README.md' 'CHANGELOG.md' 'docs/**/*.md'`
   - `lychee --config .lychee.toml 'README.md' 'docs/**/*.md'`

See `docs/internal/meta/style-guide.md` for full standards.
