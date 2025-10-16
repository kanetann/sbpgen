# Repository Guidelines

## Project Structure & Module Organization
The repository keeps scripted entry points at the top level. `sbpgen.py` reads blueprint text and renders the PDF output. Sample assets `example.txt` and `sbp.pdf` stay beside the scripts for quick visual checks, while screenshots or research notes should also live here until the layout grows more complex. When adding automated checks, create `tests/` for scenario-focused suites and store shared fixtures under `tests/fixtures/`; keep ad-hoc notebooks or scratch files out of version control.

## Build, Test, and Development Commands
Set up a Python ≥3.9 environment with `python -m venv .venv && source .venv/bin/activate` (PowerShell: `.venv\Scripts\Activate.ps1`). Install runtime dependencies with `pip install matplotlib`. Generate a baseline artifact via `python sbpgen.py --in example.txt --out sbp.pdf` (or `python sbpgen.py example.txt sbp.pdf` while the rename is pending). Run targeted automated checks using `pytest -q` or `pytest -q -k parsing` when iterating on specific scenarios.

## Coding Style & Naming Conventions
Use 4-space indentation, UTF-8 encoding, and snake_case identifiers. Break complex flows into helpers like `parse_line` or `render_lane` to keep the CLI thin. Run `black` (line length 88) before submitting patches and optionally `ruff` for linting, but avoid wholesale reformats unrelated to the change at hand. Include type hints where they clarify function contracts or CLI argument parsing.

## Testing Guidelines
`pytest` is the standard test runner; add new modules as `tests/test_*.py` and keep fixtures lightweight. Cover Unicode lane labels, customized lane ordering (Customer/Front/Back/Process), empty lanes, and uneven column widths to prevent layout regressions. Exercise CLI argument validation for missing `--in`/`--out` values and ensure malformed text inputs fail with actionable messages rather than partial PDFs.

## Commit & Pull Request Guidelines
Follow Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `test:`) with imperative subjects describing the scope. Pull requests should summarize intent, list validation commands executed (e.g., `python sbpgen.py --in example.txt --out sbp.pdf`, `pytest -q`), note the Python version and fonts available, and attach or reference the generated PDF. Link related issues or TODOs and flag follow-up items so reviewers can track outstanding design decisions.

## Security & Configuration Tips
Do not commit proprietary fonts; instead document setup steps for contributors who need them. Keep generated PDFs ignored via `.gitignore`, and ensure all input files are UTF-8 to prevent rendering errors. Revisit Python and matplotlib versions periodically, checking for CVEs before bumping dependencies or the runtime baseline.
