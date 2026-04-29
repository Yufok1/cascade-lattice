# Release Hardening

This package is a primitive dependency for Champion Council tool surfaces. Patch
releases must harden the package without breaking the imports and commands those
tools already use.

## Compatibility Contract

Before publishing a patch release, verify these surfaces still import or run:

```powershell
python -c "import cascade, cascade_lattice; from cascade import Hold, Monitor; from cascade_lattice import Hold as AliasHold; print(cascade.__version__, Hold is AliasHold)"
cascade --help
cascade-tui --help
cascade-demo --help
```

Do not remove or rename `cascade`, `cascade_lattice`, `Hold`, `Monitor`,
`cascade`, `cascade-tui`, or `cascade-demo` in a patch release.

## GitHub / PyPI Trusted Publisher

Configure the PyPI project with this trusted publisher:

- PyPI project: `cascade-lattice`
- Owner: `Yufok1`
- Repository: `cascade-lattice`
- Workflow: `publish.yml`
- Environment: `pypi`

The publish workflow should run from a GitHub release event. The publish job
should have only:

- `contents: read`
- `id-token: write`

Do not provide `password: ${{ secrets.PYPI_API_TOKEN }}` to the PyPI publish
action for normal releases.

Pin GitHub Actions to full commit SHAs in regulated release paths. Refresh the
pins only after reviewing the upstream action release notes.

## Release Gate

Run these checks from a clean checkout before tagging:

```powershell
python -m pip install --upgrade build twine
python -m pip install -e ".[dev]"
python -m compileall -q cascade cascade_lattice
python -m pytest tests -q
python -m build --sdist --wheel --outdir dist
python -m twine check dist\*
```

Inspect the artifacts:

```powershell
python -m zipfile -l dist\cascade_lattice-0.8.3-py3-none-any.whl
tar -tf dist\cascade_lattice-0.8.3.tar.gz
```

The artifacts must not include local state such as `.claude/`, `.git/`, `dist/`,
`build/`, caches, logs, local traces, or private credentials.

## Publish

Preferred path:

1. Commit the release hardening changes.
2. Push `main`.
3. Create and publish GitHub release `v0.8.3`.
4. Let `.github/workflows/publish.yml` publish through PyPI Trusted Publishing.

Manual fallback, only if Actions or Trusted Publishing is unavailable:

```powershell
python -m twine upload dist\cascade_lattice-0.8.3*
Remove-Item Env:\TWINE_USERNAME -ErrorAction SilentlyContinue
Remove-Item Env:\TWINE_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:\PYPI_API_TOKEN -ErrorAction SilentlyContinue
```

## Post-Release Verification

Use a fresh virtual environment:

```powershell
python -m venv .venv-smoke
.\.venv-smoke\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke\Scripts\python.exe -m pip install cascade-lattice==0.8.3
.\.venv-smoke\Scripts\python.exe -c "import cascade, cascade_lattice; from cascade import Hold, Monitor; print(cascade.__version__)"
```

Confirm PyPI renders these links:

- `SECURITY.md`
- `CHANGELOG.md`
- `docs/RELEASE_HARDENING.md`
- `LICENSE`
