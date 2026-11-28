# OFA capability status

Last updated: 2026-11-28. Branch: `staging`. Requirements: [MASTER_PROMPT.md](MASTER_PROMPT.md) §5.

| Mark | Meaning |
|---|---|
| ✅ Done | Ran successfully on the Windows laptop (some runs used simulated speech) |
| 🟡 Not verified | Code or model behaviour exists; not proven by a real run |
| ❌ Not done | Missing |

## Evidence behind each ✅

Each ✅ row ends with its label and the commands or tests that back it.

| Label | Meaning |
|---|---|
| `live-local` | Ran on the Windows laptop. Recorded on 2026-11-27 at `5cecce2` unless the row gives another date. The 2026-11-27 runs were **not re-run** after the 2026-11-28 changes. |
| `offline-test` | Passes against fakes, or in a headless browser on local test pages. Run on 2026-11-28. Not proof of a real run. |
| `source-inspected` | Read in the code, never run. Used for no ✅ row. |

| Ref | Reproduce command (from the repo root, `.venv-ofa/Scripts/python.exe`) |
|---|---|
| A#n | `python scripts/e2e_live.py --env-file .env`, case n (real model and desktop, simulated replies; record: [bench/generalization-2026-11-27.md](bench/generalization-2026-11-27.md)) |
| B | `python scripts/e2e_form.py --env-file .env` (real browser and model, local 6-page form, simulated replies) |
| W= | `$env:OFA_WINDOWS_TESTS=1; python -m pytest tests/ofa_core/test_windows_real.py -q` (disposable windows) |
| tests/… | `python -m pytest <ref> -q` (fakes only; it supports the row but is not the live run) |
| none recorded | Reported as run on the laptop; no command or test reference was written down. Treat as the weakest evidence. |

## Older browser engine

Rows marked **(engine)** belong to `ofa_execution/`, which the voice companion uses. The `ofa/` brain does not use it:
it works your browser through Windows. The browser rows also need the `browse` tool to be configured, and it has not
been run against these changes.

## Summary

| Category | ✅ | 🟡 | ❌ |
|---|---|---|---|
| [C1 Voice session and presence](#c1) | 6 | 10 | 5 |
| [C2 App, website and system control](#c2) | 5 | 14 | 3 |
| [C3 In-app navigation and interaction](#c3) | 8 | 14 | 3 |
| [C4 Dictation, writing and outbound messages](#c4) | 3 | 9 | 3 |
| [C5 Goal-driven search and browsing](#c5) | 2 | 7 | 3 |
| [C6 Identity, sign-in and credentials](#c6) | 1 | 15 | 8 |
| [C7 Personal data and form filling](#c7) | 8 | 14 | 6 |
| [C8 Files and documents](#c8) | 2 | 8 | 7 |
| [C9 Multi-app workflows](#c9) | 0 | 9 | 3 |
| [C10 Complex tasks: plan, approve, execute](#c10) | 4 | 4 | 3 |
| **Total** | **39** | **104** | **44** |

<a id="c1"></a>

## C1. Voice session and presence

Code: `voice/session.py, ofa/companion.py, voice/overlay.py`

### ✅ Done

- Caps Lock starts and stops a session — `live-local`: none recorded
- Caps Lock does not change typing capitalisation — `live-local`: none recorded
- Spoken requests are heard and run — `live-local`: none recorded
- Panel at the top middle of the screen — `live-local`: none recorded
- Says “Completed. Anything else?” after a verified task — `live-local`: A#1; tests/ofa_core/test_agent_graph.py::test_open_app_verified_then_completion_phrase
- Reports failure or partial success instead — `live-local`: A#2; tests/ofa_core/test_agent_graph.py::test_unverified_effect_is_not_reported_completed

### 🟡 Implemented, not verified

- Session stays open through silence and many turns
- Caps Lock kill switch cancels pending approvals
- “Stop” ends the session
- “Cancel” cancels the running task
- “Wait” / “ruko” pauses, “continue” resumes
- A new instruction replaces the running task (correction)
- Interrupting OFA while it speaks, with headphones
- “Continue the last task”, also after a restart
- Hindi completion phrase
- Addresses you by a configured name

### ❌ Not done

- Interrupting OFA while it speaks, on laptop speakers
- Separate orb looks for “acting” and “waiting for approval”
- Hinglish completion phrase
- Setting your name from the Settings page
- Pausing in the middle of a single action

<a id="c2"></a>

## C2. App, website and system control

Code: `ofa/harness/, ofa/effects/desktop.py, ofa/effects/system.py`

### ✅ Done

- Open installed apps — `live-local`: tests/ofa_core/test_agent_graph.py::test_open_app_verified_then_completion_phrase
- Find installed apps — `live-local`: W=test_windows_real.py::test_discovery_lists_installed_and_running_apps
- Open Windows Settings pages — `live-local`: A#1
- Minimize, restore, focus and close windows — `live-local`: A#2; A#3; W=test_windows_real.py::test_focus_minimize_restore_close_verified
- Confirm results from the real window state — `live-local`: W=test_windows_real.py::test_focus_minimize_restore_close_verified

### 🟡 Implemented, not verified

- Open websites and URLs
- Open files and folders
- Maximize and snap windows
- Switch browser tabs by clicking or shortcuts
- Search for files by name
- Volume, mute and media keys
- Brightness
- Lock the computer
- Read and write the clipboard
- Save a screenshot
- List and end programs
- Open Wi-Fi, Bluetooth and airplane mode pages
- Handle: app not installed, several matches, slow loading, unexpected dialog
- Report an opened website as sent, not as verified **(engine)** — `offline-test`: tests/local_execution/test_evidence_tiers.py

### ❌ Not done

- Direct on/off switching of Wi-Fi, Bluetooth and airplane mode
- Control admin windows and Windows permission prompts
- Hands folder permissions limiting what the agent can reach

<a id="c3"></a>

## C3. In-app navigation and interaction

Code: `ofa/eyes/, ofa/graphs/eyes.py, ofa/graphs/hands.py`

### ✅ Done

- Read controls and text in a window — `live-local`: A#4; W=test_windows_real.py::test_type_click_readback_on_unadapted_app
- See all visible windows with numbered marks — `live-local`: tests/ofa_core/test_eyes.py::test_marks_are_drawn_and_hidden_elements_skipped
- On-device text recognition (OCR) — `live-local`: W=test_windows_real.py::test_ocr_reads_window_text
- Vision model picks an element (practice window) — `live-local`: none recorded
- Click and type in standard Windows apps — `live-local`: A#6; W=test_windows_real.py::test_type_click_readback_on_unadapted_app
- Answer a call with “pick it up” — `live-local`: tests/ofa_core/test_eyes.py::test_pick_it_up_answers_the_call_without_a_second_yes
- Read every question on a web form page, including below the visible area — `live-local`: B
- Type into web forms, tick choices, pick from dropdowns, press Next (local test form) — `live-local`: B

### 🟡 Implemented, not verified

- Double-click and right-click
- Scroll
- Drag and drop
- Keyboard shortcuts
- Copy and paste
- Click an unlabelled icon by screen position
- Multi-step navigation
- Messaging and collaboration apps beyond calls
- Code editors, AI coding tools and terminals
- Browsers and unknown apps
- Check a click by looking for a screen change
- Refuse to click or type when the element is covered or moving **(engine)** — `offline-test`: tests/local_execution/test_browser_preflight.py; tests/local_execution/test_browser_pages.py
- Read inside same-origin frames and open shadow roots, up to 1,000 elements **(engine)** — `offline-test`: tests/local_execution/test_browser_pages.py
- Name page elements from their accessible labels **(engine)** — `offline-test`: tests/local_execution/test_browser_pages.py::test_accessible_names_and_their_source

### ❌ Not done

- App-specific adapters
- Vision model re-checking the result of a click
- Read inside closed shadow roots, or detect that one was missed **(engine)**

<a id="c4"></a>

## C4. Dictation, writing and outbound messages

Code: `ofa/dictation.py, ofa/text/, ofa/graphs/hands.py`

### ✅ Done

- Read typed text back and compare — `live-local`: A#5 (failed on 2026-11-27); W=test_windows_real.py::test_type_click_readback_on_unadapted_app
- Typing never sends by itself — `live-local`: A#6
- Compose long form answers from your profile (local test form) — `live-local`: B

### 🟡 Implemented, not verified

- Verbatim dictation (passed one live run, failed the latest)
- Spoken punctuation
- Roman or Devanagari script preference
- “What should I type?” long dictation, up to 60 seconds
- Confirm unclear names and numbers in long dictation
- Compose mode outside forms
- Revise a draft by voice
- Spoken yes before sending or posting
- Spoken yes before a risky command

### ❌ Not done

- Dictation longer than 60 seconds
- Per-word confidence checks
- Confirm unclear words inside a one-sentence command

<a id="c5"></a>

## C5. Goal-driven search and browsing

Code: `ofa/graphs/brain.py, ofa/memory.py`

### ✅ Done

- Refuses to report a near match as a match — `live-local`: A#11
- Refers back to an earlier window (“bring it back”) — `live-local`: A#3

### 🟡 Implemented, not verified

- Repeat until a condition is met
- Scroll through results
- Compare candidates against all criteria
- Stop on loops
- Stop when you interrupt, results end or it is blocked
- Remember results for “that one” / “the second one”
- Save, view and delete learned names

### ❌ Not done

- Dedicated pagination and filtering engine
- Searches longer than 25 steps
- Contacts and roles import

<a id="c6"></a>

## C6. Identity, sign-in and credentials

Code: `ofa/vault/, ofa/effects/credentials.py`

### ✅ Done

- Take the page address only from the browser's own address bar (Edge and Chrome windows, local test page) — `live-local`: 2026-11-28, results in [API pull request 38](https://github.com/OFA-Labs/one-for-all-api/pull/38); tests/ofa_core/test_browser_identity.py

### 🟡 Implemented, not verified

- Add, revoke and delete private items from E-Brain → Info corpus
- Every use of a private item asks aloud with item, website, field and security
- Use a private item inside a form, only on its saved website
- Hand a form's human check to you and continue
- Encrypted vault and enrollment page
- Unlock with the Windows password
- Secrets handled as handles the model cannot read
- Check the real website or app before filling
- Refuse look-alike domains
- Bitwarden and 1Password command-line support
- Fill a login on a real site
- Ask which account
- Approval for account or password changes
- Refuse to fill a private item when the page shows another account — `offline-test`: tests/ofa_core/test_expected_account.py
- Set that account from E-Brain → Info corpus → Private — `offline-test`: web repo `tests/info-corpus.spec.ts` (fake companion)

### ❌ Not done

- Complete sign-in flows end to end (including single sign-on)
- Password-manager browser autofill
- Detect passkey or 2FA and resume afterwards
- One-time code from email
- One-time code from phone messages
- Windows Hello unlock on this laptop
- Fill private items where no address bar can be read, such as Edge in full screen (refused on purpose)
- Check the address-bar rule in Firefox

<a id="c7"></a>

## C7. Personal data and form filling

Code: `ofa/graphs/form.py, ofa/forms.py, ofa/eyes/form.py, ofa/corpus/`

### ✅ Done

- Fill a 6-page form by voice from your profile and submit it (local test form, about 78 s) — `live-local`: B
- Info corpus “Use without consent”: Markdown profile and resume — `live-local`: B; tests/ofa_core/test_corpus.py
- Identity fields filled straight from the profile — `live-local`: B; tests/ofa_core/test_form_graph.py::test_identity_fields_need_no_model_call
- Match other questions to profile facts with the model — `live-local`: B
- Text, long text, radio, checkbox, dropdown and conditional questions — `live-local`: B; tests/ofa_core/test_form_graph.py::test_conditional_question_that_appears_after_a_choice
- Ask for missing answers and personal decisions by voice — `live-local`: B; tests/ofa_core/test_form_graph.py::test_personal_decisions_are_always_asked
- Never tick a declaration without a spoken yes — `live-local`: B; tests/ofa_core/test_form_graph.py::test_declaration_is_always_asked_and_never_ticked_on_no
- Speak a summary and wait for a spoken yes before submitting — `live-local`: B; tests/ofa_core/test_form_graph.py::test_not_submitted_without_a_spoken_yes

### 🟡 Implemented, not verified

- Google Forms
- Microsoft Forms
- Read validation errors after Next and ask for a correction
- Never fill password, ID or bank fields from the model
- Offer to save new answers for next time
- Speed mode wording
- Refuse to submit the same form twice
- Closed form message
- Keep going and ask you when the model is unavailable
- Block invented numbers and assumed “Nil” or “No” answers
- Store private personal fields in the vault
- Confirm submission from the page address, not the “response recorded” wording alone — `offline-test`: tests/ofa_core/test_form_graph.py::test_a_confirmation_address_proves_submission_without_the_phrase; tests/ofa_core/test_form_graph.py::test_the_phrase_alone_is_not_proof_and_is_never_resubmitted; tests/ofa_core/test_form_graph.py::test_an_error_page_at_a_new_address_is_not_proof
- Read every filled value back before Next or Submit, and stop on a mismatch — `offline-test`: tests/ofa_core/test_form_graph.py::test_a_value_the_page_changes_is_not_reported_as_filled; tests/ofa_core/test_form_graph.py::test_an_option_that_does_not_tick_is_not_submitted; tests/ofa_core/test_form_graph.py::test_a_private_value_is_never_read_back_or_stored
- Ask for each field when a page repeats the same question — `offline-test`: tests/ofa_core/test_form_graph.py::test_two_fields_with_the_same_question_are_asked_not_guessed

### ❌ Not done

- File upload questions
- Date and grid questions
- Forms inside native (non-browser) apps
- Check adjectives and claims in composed answers against the profile
- Go back to an earlier page to fix an answer
- Show the filled form on screen for review

<a id="c8"></a>

## C8. Files and documents

Code: `ofa/effects/files.py`

### ✅ Done

- Search a named folder — `live-local`: A#9
- Create a text file after a spoken yes — `live-local`: A#7; A#8

### 🟡 Implemented, not verified

- Ask before searching a private place you did not name
- Read plain-text files (first 8 KB)
- Overwrite a text file
- Ask which file when several match, or say none
- Refuse to read credential files
- Cloud drives and email attachments through their screens
- Spoken yes before upload, attach or share
- Check a written file against its exact expected content **(engine)** — `offline-test`: tests/local_execution/test_evidence_tiers.py::test_file_text_is_checked_by_verify

### ❌ Not done

- Read PDF, Word or Excel files directly
- Create PDF, Word or Excel files
- Direct cloud drive or email connection
- Attach a file to a form
- Open a preview of the exact file before sharing
- Verify the right file was attached
- Ask again if the file changed

<a id="c9"></a>

## C9. Multi-app workflows

Code: `ofa/graphs/, ofa/memory.py`

### ✅ Done

- None

### 🟡 Implemented, not verified

- Chain steps across apps
- Pass data between apps
- Plain-text deliverables
- Track each destination separately
- Report partial success
- Block repeating a completed send
- Send to real outside destinations
- Read-only commands for code review
- Spoken yes before comment, push or merge

### ❌ Not done

- Deliverables in other formats
- Isolated environment for untrusted code
- Phone as a source or destination

<a id="c10"></a>

## C10. Complex tasks: plan, approve, execute

Code: `ofa/graphs/hands.py`

### ✅ Done

- Require a plan before a second risky step — `live-local`: A#12; tests/ofa_core/test_agent_graph.py::test_plan_required_for_multiple_consequential_steps
- Wait for spoken approval of the plan — `live-local`: tests/ofa_core/test_agent_graph.py::test_plan_spoken_and_approved_then_each_action_still_asks
- Still ask at each risky step — `live-local`: tests/ofa_core/test_agent_graph.py::test_plan_spoken_and_approved_then_each_action_still_asks
- Progress updates page by page while filling a form — `live-local`: B

### 🟡 Implemented, not verified

- Read the plan aloud
- Change the plan by voice and ask again
- Remember sent actions across a restart; keep unknown outcomes blocked for 24 hours **(engine)** — `offline-test`: tests/local_execution/test_ledger.py
- Count a step as complete only after reading its result back **(engine)** — `offline-test`: tests/local_execution/test_evidence_tiers.py

### ❌ Not done

- Announce that a plan is being built
- Progress updates outside form filling
- Ask again when scope or risk changes
