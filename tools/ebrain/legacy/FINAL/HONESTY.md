# E-Brain: the honest one-pager

**What it is.** E-Brain is a shared notebook for your AI helpers: Claude Code, Codex and the ONE FOR ALL voice agent. When one of them learns or decides something ("the auth token lasts 30 minutes"), it writes it down. Later, every helper gets the latest version of the facts it needs, and sees where each fact came from. Nothing is ever overwritten. Every change is a new entry, so you can look back or undo. It runs on your laptop in one file, with no paid service and no AI model inside it. **It is EXPERIMENTAL.**

## What "1,000 memories" means

A memory is one saved entry: one note, decision, file version or log entry from any helper. Changing a fact adds a new memory, so a fact edited 5 times counts as 5.

| How you work | 1,000 memories lasts about |
|---|---|
| 3 helpers saving only durable notes, about 40 a day | 25 days |
| Heavy use, about 300 a day | 3 days |

Up to about 1,000 memories per project it works *reasonably* well. Beyond that it is unreliable; that is a known limitation of the project as of now. It keeps working past 1,000, but every answer is then marked "beyond tested range". The website shows a meter, for example "412 / 1,000 memories", which turns amber at 800 and red at 1,000.

## What it can do (measured on synthetic test data)

- **Keeps the newest value.** If Claude wrote "TTL 60 min" on Monday and Codex wrote "30 min" on Wednesday, you see 30 min, and the history shows both. At 1k memories this was right 86–95% of the time.
- **Refuses to let web pages or tool output overwrite your decisions.** Such content is shown only as "UNTRUSTED". Attacks succeeded 0% of the time in every run.
- **Keeps a helper's private notes private** from the other helpers. There were 0 leaks in every run.
- **Undo.** Rolling back to a moment gives exactly the answers you had then, in every run.

## What it can't do reliably

- **Two helpers word the same fact differently.** It may show BOTH as current until you confirm which is right. An outdated value was still shown as current in 8–28% of questions at 1k memories, and in 56–65% at 10k.
- **Helpers write different values at the same moment.** It should flag a conflict. It did so correctly 50–100% of the time at 1k, and 47–68% at 10k.
- **Vague questions** like "what's the TTL?" when several exist: you may get only some of them.
- **Automatic self-repair** hid correct memories in tests: 0–17% of the time at 1k and 73–83% at 10k. So it is **switched to "approval required"**: it suggests a change, and nothing happens until you click Approve.

## What is untested

- No numbers come from real use. Every number above comes from a synthetic benchmark with made-up projects.
- An experimental "these two might be the same fact" detector was built and measured. It did not reduce outdated answers at all, so it is **OFF**. When switched on, only about 1 in 3 of the pairs it flagged were really the same fact at 10k memories, so it never merges anything without you.
- Durability after a power cut has not been tested. It is tested when a program is killed, and nothing was lost.

**Developers:** every unproven function in the code carries `# UNTESTED:` with the test that would settle it, and every capacity limit carries `# LIMIT:`. A test fails the build if one is missing. The sources for every number are in `FINAL/12-limits-and-non-goals.md` and `FINAL/reference/results/RESULTS.md`.
