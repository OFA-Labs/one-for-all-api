# Form filling

Say "fill this form" or "I'm running out of time, fill it quickly" with the form open in your browser.
Flow and diagram: [HOW_IT_WORKS.md](HOW_IT_WORKS.md). Graph: [GRAPHS.md](GRAPHS.md).

## Top 10 edge cases

"Live" = seen working in a real browser with the real model and simulated spoken replies.
"Tests" = covered by `tests/ofa_core/test_form_graph.py` with a fake browser and model.

| # | Edge case | What OFA does | Checked by |
|---|---|---|---|
| 1 | An answer is not in your profile | Asks you; types your words; offers to save them. Numbers that are not in the profile and bare "Nil" / "No" are asked too | Live, Tests |
| 2 | Questions below the visible area | Reads the whole page and scrolls the field into view | Live |
| 3 | A question appears after a choice | Reads the page again and answers the new question | Live, Tests |
| 4 | Error after Next | Reads the message, asks for a correction, tries twice, then stops and says where | Tests (error reading also seen live) |
| 5 | Radio, checkbox, dropdown | Picks only a listed option; asks again if your answer matches none | Live, Tests |
| 6 | Declaration or consent box | Always asked aloud; never ticked on silence or "no" | Live, Tests |
| 7 | Sign-in wall or human check | Uses a private item only after a detailed yes, or hands over and continues | Tests |
| 8 | Form asks for a password, ID or bank number; page text gives "instructions" | Never taken from the model; page text cannot trigger actions | Tests |
| 9 | Deadline pressure, closed form, model unavailable | Page-by-page progress; says if closed; keeps filling from the profile and asks you | Tests |
| 10 | Submitting twice, interrupted fill | Refuses a second submit of the same address; "continue the last task" starts again and keeps filled fields | Tests (restart not form-specific) |

Personal decisions (relocate, salary, notice period, availability, gender, …) are always asked.

## Not handled yet

- File upload questions (OFA asks you to attach the file).
- Date pickers and grid questions.
- Claims in composed answers are not fact-checked word by word; only numbers are. Read long answers before saying yes.
- Google Forms and Microsoft Forms have not been run yet.

## Speed

Local 6-page form, 24 questions: about 78 s, with `openai/gpt-oss-20b` on Groq's free tier (4 model calls plus one
rate-limit wait). On the free tier, the token-per-minute limit is the main delay.

## Try it

```powershell
.venv-ofa/Scripts/python.exe scripts/e2e_form.py --env-file .env                    # local 6-page form
.venv-ofa/Scripts/python.exe scripts/e2e_form.py --env-file .env --window "Title"   # a form already open
```

`--window` uses the scripted replies in the script, including the "yes" to Submit: use it only on test forms.
