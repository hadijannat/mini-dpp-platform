# Release Guide

This guide documents how to cut a release and publish build artifacts.

## Versioning
- Update versions in:
  - `backend/pyproject.toml`
  - `frontend/package.json`
  - `backend/app/core/config.py` (API version string)
- Update `CHANGELOG.md` with a dated release section.

## Build and publish container images
Example for GitHub Container Registry (GHCR):

```bash
# Login once
export GHCR_OWNER=<org-or-user>
export VERSION=v0.1.0

docker login ghcr.io

# Build
DOCKER_BUILDKIT=1 docker build -t ghcr.io/${GHCR_OWNER}/mini-dpp-backend:${VERSION} ./backend
DOCKER_BUILDKIT=1 docker build -t ghcr.io/${GHCR_OWNER}/mini-dpp-frontend:${VERSION} ./frontend

# Push
docker push ghcr.io/${GHCR_OWNER}/mini-dpp-backend:${VERSION}
docker push ghcr.io/${GHCR_OWNER}/mini-dpp-frontend:${VERSION}
```

## SBOM and security scan
- The `Security` workflow generates an SBOM and runs Trivy scans.
- Review uploaded artifacts before publishing a release.

## GitHub release checklist
1. Ensure CI is green (tests, lint, build, security scans).
2. Tag the release:

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

3. Create a GitHub Release and attach:
   - Release notes (from `CHANGELOG.md`)
   - SBOM artifact(s)
   - Smoke test report (if available)

## Notes
- Do not commit `.env` files.
- Production deployments should override default secrets and credentials.
