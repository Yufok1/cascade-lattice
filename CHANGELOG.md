# Changelog

## 0.8.4 - 2026-05-01

- Added OpenAI Responses API receipt support to the OpenAI patch surface.
- Preserved Chat Completions and legacy Completions receipt behavior.
- Added no-cost OpenAI acclimation docs and fake-client tests with no live API calls.
- Captured Responses input/output token usage where present.
- Kept OpenAI API keys optional and required only for user-run live OpenAI calls.

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
