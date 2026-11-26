# Contributing

## Never commit
Credentials or `.env` files (only `*.example` templates with empty values), virtual environments, caches,
logs, audio or video captures, generated reports, or local notes. Check with `git check-ignore -v <path>`.

## Branches and commits
Branch `type/short-slug`; commit `type(scope): summary` (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`).
Open pull requests against `staging`, one logical change each.

## Before opening a pull request
```powershell
git status --porcelain
git diff --cached --stat
python -m pytest tests/ofa_core -q          # in the OFA environment, see docs/ofa/README.md
```

## Paths that tests or scripts depend on
`docs/ebrain/implementation-plan/README.md` and `STATUS.md`, `TRACEABILITY.csv`, `CHECKPOINTS.csv`,
`evidence/**`, `tools/ebrain/legacy/**`, and the sibling web repo's `docs/SPEC_ITERATION_1.md` and `AGENTS.md`.

Naming and architecture rules: `docs/ofa/ARCHITECTURE.md`.
