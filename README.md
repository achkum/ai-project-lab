# Research & Build Lab

Local-first daily discovery and rolling project delivery, with a public GitHub Pages dashboard and private GitHub decisions.

## What runs
- 30 bounded public RSS/Atom/API collectors, metadata deduplication, provenance and honest seven-day coverage.
- SQLite selection state, immutable candidate scope, one active shortlist per lane, owner-only GitHub commands, and a 24-hour recommended default.
- Leased workers with checkpoint/finish fencing, isolated workspace preparation, and subscription-backed Codex CLI adapter.
- Allowlisted public status export; detailed options and evidence stay in the private companion repository.
- Native Codex scheduled runs operate the pipeline while this laptop and the app are awake.

No paid API fallback or credit purchase. GPT-6 Astra for analysis/review; GPT-6.1 Terra for implementation; deterministic code for collection and state transitions. Fresh allowance checks fail closed when credit availability or quotas are unknown. This is not an account billing-settings lock.

## Run locally
Use Python 3.10+ (install tzdata if your Windows Python lacks timezone data), GitHub CLI authenticated as the owner, and Codex CLI authenticated with ChatGPT. Create ignored config/profile.local.json using config/local-runtime.example.json. Keep runtime databases outside this public repo, in the private companion repo.

    python -m engine.lab collect
    python -m engine.lab status
    python -m engine.lab cycle
    python -m engine.lab export
    python -m engine.lab backup

Run tests:

    python -m unittest discover -s tests -p "test_*.py" -v
    node tests/status.test.cjs

Private RUNBOOK.txt contains daily analysis, publication, worker execution, review and recovery instructions. The scheduler's model host supplies current account-usage proof before the subscription adapter runs; these proofs are ignored local runtime files.

## Choose a direction
Open a shortlist from the dashboard and comment using its /lab commands. Select, hold, refine, request more, save, reject or resume. Without a response, the eligible recommendation starts on the next successful check after 24 hours. A change during execution revokes the worker lease and pauses for a checkpoint. If GitHub cannot be checked, no automatic selection proceeds.

## Operational limits
A sleeping/offline laptop delays work and leaves a stale dashboard. Backups currently remain on the same laptop. Source-channel counts differ from independent source-family counts. Evidence is a lead, not validated demand or novelty. Deployment and user-journey checks remain agent-mediated; code generation is not a production guarantee.

GitHub Pages publishes docs/ from main. Runtime records, credentials, private candidate descriptions and employer data must never enter this repository. The old engine.queue smoke queue remains separate from the operational workflow state machine.
