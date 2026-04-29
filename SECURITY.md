# Security Policy

## Supported Versions

Security fixes are issued for the latest published minor line. Older releases are
best-effort only unless a downstream deployment has a written support agreement.

| Version | Supported |
| --- | --- |
| 0.8.x | Yes |
| < 0.8 | Best effort |

## Reporting a Vulnerability

Report suspected vulnerabilities through GitHub Security Advisories:

https://github.com/Yufok1/cascade-lattice/security/advisories/new

If advisories are unavailable, open a minimal public issue that says a private
security report is needed. Do not post tokens, exploit payloads, private model
outputs, customer data, or internal Champion Council traces in a public issue.

## Runtime Boundary

`cascade-lattice` is embedded in Champion Council primitive tool surfaces,
including observation, advanced control, safety, HOLD protocol, diagnostics,
status/introspection, visualization, and snapshot flows. Patch releases must
preserve the public import and command surface unless the change is a direct
security fix:

- `import cascade`
- `import cascade_lattice`
- `from cascade import Hold, Monitor`
- `from cascade_lattice import Hold, Monitor`
- `cascade`
- `cascade-tui`
- `cascade-demo`

Potentially breaking security changes require a minor or major version bump and
a migration note in `CHANGELOG.md`.

## Supply-Chain Controls

The release workflow is designed for PyPI Trusted Publishing through GitHub OIDC.
Long-lived PyPI API tokens should not be stored in GitHub Actions secrets for
the normal release path.

Release artifacts must pass:

- module compilation for `cascade` and `cascade_lattice`
- test suite execution
- wheel and source distribution build
- `twine check`
- pinned GitHub Actions references in the publish workflow
- artifact inspection for accidental local state such as `.claude/`, `dist/`,
  caches, logs, or private traces

Manual uploads are allowed only as a fallback. Clear local upload credentials
from the shell immediately after use.
