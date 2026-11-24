# E-Brain implementation decisions

## 2026-11-24 — M0 scaffold

- The M0 acceptance command deliberately exits with failing tests. Its required
  result is 52 collected: 22 failed, 6 passed, 1 skipped and 23 errors. The general
  requirement for a green backend suite applies from M1; replacing the stub early
  would violate M0. No test is changed, weakened or newly skipped.
- Copy the reference package, all seven Python test files and requirements
  byte-for-byte. During M0 only, `ebrain/store.py` is the supplied
  `FINAL/reference/m0_store_stub.py`; it raises `NotImplementedError("M1")`.
  The real store and its honesty tags arrive in M1, so T-051 and T-052 remain red
  as specified. Do not add behavior or tags to change this checkpoint.
- `pyproject.toml` repeats all 23 supplied dependency pins and restricts Python
  to 3.12. It uses `tool.uv.package = false`: M0 runs the package from the repo
  root and needs no additional build dependency. Install using the exact
  `requirements.txt` command from the spec.
- The existing backend is a clean README-only checkout; `origin/staging` and
  `main` both start at `67234807075b93ed024005d0da29ad6deaea0c46`.
  Work uses `feat/ebrain-m0`, based on `origin/staging`.
- GitHub reports `OFA-Labs/one-for-all-api` as public. Publishing was initially
  paused because the original instruction required private repos. On 2026-11-24
  the owner explicitly overrode that requirement: keep this repo public and
  publish the contribution PR as `jvsing` to `OFA-Labs`. The GitHub connector
  authenticates as `jvsing`; the CLI authenticates as `OFA-Labs`. Push the feature
  branch using the authorized CLI credentials, create the PR as `jvsing` against
  `OFA-Labs/one-for-all-api:staging`, and leave it unmerged for the owner.
- The web checkout is clean on `feat/icon-navigation-native-engine`; M0 changes
  no web source. Run the requested existing web checks as a baseline using the
  production Playwright server on port 3100. Do not start a development server.
- Existing paths verified before editing: backend `README.md` contains the
  three-line initial description. The frontend `AGENTS.md` has the nine-line
  generated Next.js block described by the spec. Installed Next.js Playwright
  and installation guides were read before web verification.

### M0 validation (2026-11-24)

Commands run from `one-for-all-api`:

| Command | Observed result |
| --- | --- |
| `uv venv --python 3.12 .venv` | Created CPython 3.12.10 environment; exit 0. |
| `uv pip install --python .venv\Scripts\python.exe -r requirements.txt` | 23 pinned packages installed; exit 0. |
| `.venv\Scripts\python.exe -m pytest tests -q` | **22 failed, 6 passed, 1 skipped, 23 errors**, 1 warning, in 8.66s; expected exit 1. |
| `.venv\Scripts\python.exe -m pytest tests --collect-only -q` | **52 tests collected** in 0.75s; exit 0. |

A Python integrity check compared SHA-256 hashes for all 14 copied files
(six package files including the stub, seven test files and requirements).
Every copy matched byte-for-byte. It also compared all 23 requirements with
`pyproject.toml` and installed versions using `importlib.metadata`; all matched.
The one backend warning is the reference's known Starlette/httpx deprecation.
The CSV comparison is the reference's existing skip, not an added skip.

Commands run from `one-for-all-web` (no web implementation in M0):

| Command | Observed result |
| --- | --- |
| `npm run build` | Passed; 22 static pages generated; exit 0. |
| `npx tsc --noEmit` | Passed; exit 0. |
| `npm run lint` | 0 errors, 2 existing warnings in `.cache/motion/patch-duration.mjs`; exit 0. |
| `npm run check:arch` | 0 dependency violations; 87 modules, 180 dependencies; exit 0. |
| `npx playwright test tests/journeys.spec.ts tests/quality.spec.ts` | **17 passed** in 41.4s; exit 0. |

There is no `tests/e-brain.spec.ts` until M1, as specified. The known failing
dictation-hotkey test was not run or modified. Restore generated tracked
screenshots and `next-env.d.ts` before committing. M0 has no working store:
memory writes, queries, isolation, persistence, healing and joins remain
unverified in this port until M1. Frontend memory UI, agent hooks, voice bridge
and the real-port ablation remain future milestones.
