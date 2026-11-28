# OFA capability status

Last updated: 2026-11-27. Branch: `feat/info-corpus`. Requirements: [MASTER_PROMPT.md](MASTER_PROMPT.md) §5.

| Mark | Meaning |
|---|---|
| ✅ Done | Ran successfully on the Windows laptop (some runs used simulated speech) |
| 🟡 Not verified | Code or model behaviour exists; not proven by a real run |
| ❌ Not done | Missing |

## Evidence behind each ✅

Each ✅ row ends with its label and the commands or tests that back it.

| Label | Meaning |
|---|---|
| `live-local` | Ran on the Windows laptop, as recorded on 2026-11-27 at `5cecce2`. **Not re-run since**, so later changes are not covered. |
| `offline-test` | Passes against fakes only. Re-run on 2026-11-28 with the browser and trust fixes of that date. |
| `source-inspected` | Read in the code, never run. Used for no ✅ row. |

| Ref | Reproduce command (from the repo root, `.venv-ofa/Scripts/python.exe`) |
|---|---|
| A#n | `python scripts/e2e_live.py --env-file .env`, case n (real model and desktop, simulated replies; record: [bench/generalization-2026-11-27.md](bench/generalization-2026-11-27.md)) |
| B | `python scripts/e2e_form.py --env-file .env` (real browser and model, local 6-page form, simulated replies) |
| W= | `$env:OFA_WINDOWS_TESTS=1; python -m pytest tests/ofa_core/test_windows_real.py -q` (disposable windows) |
| tests/… | `python -m pytest <ref> -q` (fakes only; it supports the row but is not the live run) |
| none recorded | Reported as run on the laptop; no command or test reference was written down. Treat as the weakest evidence. |

## Summary

| Category | ✅ | 🟡 | ❌ |
|---|---|---|---|
| [C1 Voice session and presence](#c1) | 6 | 10 | 5 |
| [C2 App, website and system control](#c2) | 5 | 13 | 3 |
| [C3 In-app navigation and interaction](#c3) | 8 | 11 | 2 |
| [C4 Dictation, writing and outbound messages](#c4) | 3 | 9 | 3 |
| [C5 Goal-driven search and browsing](#c5) | 2 | 7 | 3 |
| [C6 Identity, sign-in and credentials](#c6) | 0 | 13 | 6 |
| [C7 Personal data and form filling](#c7) | 9 | 11 | 6 |
| [C8 Files and documents](#c8) | 2 | 7 | 7 |
| [C9 Multi-app workflows](#c9) | 0 | 9 | 3 |
| [C10 Complex tasks: plan, approve, execute](#c10) | 4 | 2 | 3 |
| **Total** | **39** | **92** | **41** |

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

### ❌ Not done

- App-specific adapters
- Vision model re-checking the result of a click

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

- None

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

### ❌ Not done

- Complete sign-in flows end to end (including single sign-on)
- Password-manager browser autofill
- Detect passkey or 2FA and resume afterwards
- One-time code from email
- One-time code from phone messages
- Windows Hello unlock on this laptop

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
- Confirm the “response recorded” page — `offline-test`: tests/ofa_core/test_form_graph.py::test_a_confirmation_address_proves_submission_without_the_phrase; tests/ofa_core/test_form_graph.py::test_the_phrase_alone_is_not_proof_and_is_never_resubmitted

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

### ❌ Not done

- Announce that a plan is being built
- Progress updates outside form filling
- Ask again when scope or risk changes
