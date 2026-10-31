# Research & Build Lab

**[Open the dashboard →](https://achkum.github.io/ai-project-lab/)**

[Thesis possibilities](https://achkum.github.io/ai-project-lab/#thesis) · [Project possibilities](https://achkum.github.io/ai-project-lab/#projects) · [Source library](https://achkum.github.io/ai-project-lab/#sources)

Daily broad discovery and independently queued research/build jobs. Visual cards show their sources, existing work, proposed contribution, model/data choices and uncertainty.

## Start work from the dashboard

1. Connect the browser once using your private dashboard key. Retrieve it locally with python -m engine.dashboard_key; never share or commit it.
2. Select any combination of cards. Use **Investigate selected** or **Build selected** and confirm the scopes.
3. Each option becomes a separate durable job. The VPS accepts requests while your laptop is off; the laptop processes one at a time when awake.
4. Monitor live status, pause/cancel individual jobs, resume blocked work and open private review artifacts.

This uses dedicated key pairing, not GitHub OAuth. The key stays in the browser tab's session storage and expires after 90 days. No ChatGPT, GitHub or SSH credential goes into the page or VPS. The HTTPS endpoint uses an IP-based sslip.io hostname; DNS and certificate availability are dependencies.

Thesis jobs produce investigation briefs, not complete theses. Project jobs produce bounded drafts. **Review ready is not a production release.** The strongest-model/agent review validates results before promoting a demo.

## Discovery and provenance

35 configured RSS/Atom/API channels span research and practitioner/consumer communities. Successful channels and independent source families are shown separately. Topics include vision, audio, time series, tabular prediction, transfer learning, active learning, edge models, LLMs and non-AI methods; these are seeds, not a closed list.

Every option distinguishes the source finding, existing solution, proposed extension and novelty uncertainty. Technical feasibility does not prove customer demand. Existing tutorials and model architectures are explicitly credited.

## Runtime

- VPS: daily collector plus authenticated SQLite job API behind Caddy HTTPS.
- Laptop: serial worker, explicit scoped Windows sandbox, fresh subscription checks before every model call.
- GPT-6 Astra: investigation and review. GPT-6.1 Terra: implementation. No paid API fallback, purchases or quota resets.
- Scheduled Codex research/review follows the private RUNBOOK.txt. A published 24-hour recommendation policy remains the fallback when there is no owner selection or hold.

The old single-choice workflow database and GitHub issues remain history. The VPS multi-job queue is authoritative for execution.

## Local setup and checks

Use Python 3.10+, GitHub CLI authenticated as the owner, Codex CLI signed into ChatGPT and the existing SSH alias. Configure ignored config/profile.local.json, including absolute runtime/private/public paths and codex_executable. Model credentials stay local.

    python -m engine.allowance
    python -m engine.lab collect
    python -m engine.lab export
    python -m engine.job_worker --once
    powershell -NoProfile -File deploy/install-laptop-worker.ps1

The scheduled worker starts at Windows sign-in. Keep the laptop awake for model work. Source collection and queued requests survive laptop shutdown. There is no paid compute budget for model training; model/data downloads and local resource needs require an explicit feasibility check.

    python -m unittest discover -s tests -q
    node tests/status.test.cjs

GitHub Pages publishes docs/ from main. Never commit runtime databases, private keys, account proofs or employer data. Private review bundles live in the companion thesis repo.

## Discuss or change direction now

**Ask about this idea**, **Refine this direction** and **Find different ideas** prepare a message to paste into the Codex chat for immediate discussion. Those discussion controls are not a hosted chatbot; the start buttons are real queue actions. Questions preserve selections. Explicit refinements pause only affected work, and one-off preferences are not silently made permanent.
