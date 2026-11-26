# C2 — Application, Website, System Control
**Purpose:** §5 C2 · **Depends on:** 07 · **Files likely touched:** `api/ofa/harness/*`, `api/voice/discovery.py`, `api/ofa_execution/{windows,native_launch,websites}.py` · **Done when:** M05 rows H1–H5 pass.

- Discovery: installed apps (`shell:AppsFolder`, App Paths, Start Menu .lnk) + running windows; cached 10 min; reuse `voice/discovery.py`.
- Verbs: open; close (WM_CLOSE; unsaved-changes dialog → ask); switch/focus (SetForegroundWindow + AttachThreadInput); arrange (SetWindowPos / snap); search (Windows search or in-app); settings via `ms-settings:` URIs (security/permission changes = Tier 2).
- Websites: browse adapter (verified tab URL) else default-browser launch verified by address bar via UIA.
- Failures: NOT_INSTALLED (offer store/web), LOADING (wait ≤ 20 s), AMBIGUOUS (spoken choice), DIALOG (describe + ask), PERMISSION/UAC (handoff).
- Verify from system state: process + visible window + title/URL match.
