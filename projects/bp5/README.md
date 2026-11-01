# Prata — Swedish practice for real situations

**[Open Prata](https://198.44.116.159.sslip.io/apps/bp5/)**

Practise before a real interaction: buy the right ticket, explain a wrong order, ask a colleague for help or discuss a problem. The mobile web app has **18 situations and 54 different guided tasks**: eight Basic situations, six Medium and four High, with three tasks in each. Finishing one offers a different task. It runs on the existing VPS; the laptop can be off.

Speak or type, listen to the character, then practise related listening, reading and writing. Save phrases, return to a session and revisit earlier work. Speech transcripts are editable before sending. Conversations use authored responses and bounded matching. If the app misses a valid reply, choose the meaning you intended to continue; your original reply is preserved and this help is recorded. This is guided practice, not unrestricted conversation or automatic grammar assessment. [Language checks and their limits](content/language_quality_report.json) include the poor coverage of previously unseen wording.

## Your account

Create an account using an invitation and your own password. Save the one-use recovery codes shown at signup. Accounts have separate history, SFI settings and exports. Recovery invalidates earlier sessions; recovery codes can be regenerated. Export and account deletion are available in Settings. No email address or Google/API account is required.

Recordings are deleted after processing. Transcripts and practice history stay in your account until deleted. The daily VPS backup schedule retains encrypted copies for at most seven days. Offline laptop copies are pruned on the next successful sync, so an unavailable laptop delays their removal. The decryption key is kept separately from the VPS. There is no ad tracking or paid cloud inference.

## SFI and learning claims

The app records practice against selected, source-linked SFI components; it does not award grades, decide placement or infer mastery from completion. Basic/Medium/High are task difficulty, not SFI A/B/C. The current consolidated syllabus and the framework applying to education beginning after 31 December 2026 remain separate. Existing sessions retain their original content and criterion snapshots.

The 54 tasks are original authored examples. Official syllabus sources establish the criteria, not validation of these mappings. Remembering through meaningful situations and feelings is a design hypothesis, not a measured learning benefit. Educator review and learner-effectiveness trials remain outstanding.

## Operate and verify

Production uses `server/run.py` → `server/production.py`, an isolated SQLite volume, and local Swedish speech models. **Do not expose the historical `server/app.py` service.** See [the production runbook](server/PRODUCTION-RUNBOOK.md), [deployment operations](deploy/OPERATIONS.md), and [third-party credits](THIRD-PARTY-NOTICES.md).

The container is limited to 1536 MiB, 1.8 CPUs and one speech job at a time. This is a small-server installation, not an unlimited-concurrency promise. The service uses secure cookies, CSRF/origin checks, invitation-only signup, password hashing and account-scoped APIs. Start with invited users; public registration is not enabled.

Checks: `python -m unittest discover -s tests -p "test*.py"`, `node --test tests/frontend.test.cjs`, `python content/validate_library.py`. Install the pinned `server/requirements.txt` in a virtual environment first. Actual Linux voice, HTTPS, restart and backup checks are recorded separately from deterministic fixtures. Public read-speech samples do not establish accuracy for SFI learners, accents or real phone microphones.

Historical local progress is preserved separately. An operator can import it only into an explicitly named account using `server/manage.py import-legacy`; it is never assigned automatically to the first registrant.
