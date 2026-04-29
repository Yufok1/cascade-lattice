# Changelog

## 0.8.3 - 2026-04-29

- Hardened the PyPI release workflow around GitHub OIDC Trusted Publishing.
- Removed the normal-release dependency on a long-lived `PYPI_API_TOKEN`.
- Pinned GitHub Actions in the publish workflow to exact commit SHAs.
- Added a security policy for vulnerability reporting, runtime compatibility,
  and supply-chain controls.
- Added a release hardening checklist for build, test, artifact inspection, and
  post-release verification.
- Added PyPI-safe project metadata links for security and release hardening
  documentation.
- Added the advertised `cascade-demo` console entry point.
- Preserved runtime import compatibility for `cascade` and `cascade_lattice`.

## 0.8.2 and earlier

- Existing provenance, HOLD, diagnostics, store, visualization, and TUI surfaces.
