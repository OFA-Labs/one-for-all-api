# C8 — Files and Documents
**Purpose:** §5 C8 · **Depends on:** 04, 07 · **Files likely touched:** `api/ofa_execution/files.py`, `api/ofa/files_search.py` · **Done when:** M08 rows L1–L6 pass.

- Sources: local allowed roots; Google Drive / OneDrive via signed-in web session or sync folder; email attachments via web session. Searching a private source the user did not open = Tier 2 ("May I search Downloads and Drive for your resume?").
- 0 matches → say so; > 1 → list name, folder, modified date; ask.
- Before upload/attach/share: open preview, speak name + size + date, Tier 2 with `file_sha256` in the digest.
- After attach: verify the filename in the target UI; hash change → new approval.
