# Research & Build Lab

**[Open the dashboard â†’](https://achkum.github.io/ai-project-lab/)**

[Thesis possibilities](https://achkum.github.io/ai-project-lab/#thesis) Â· [Project possibilities](https://achkum.github.io/ai-project-lab/#projects) Â· [Source library](https://achkum.github.io/ai-project-lab/#sources)

Daily broad discovery and independently queued research/build jobs. Visual cards show their sources, existing work, proposed contribution, model/data choices and uncertainty.

## Start work from the dashboard

1. Set your own password using the private, one-hour setup invitation opened by the agent. Then use **Sign in** on the dashboard and optionally **Remember this browser**.
2. Select any combination of cards. Use **Investigate selected** or **Build selected**. There is no additional confirmation or draft-approval step.
3. Each option becomes a separate durable job. The VPS accepts requests while your laptop is off; four managed laptop slots process independent jobs when awake.
4. Monitor live status, pause/cancel individual jobs, resume blocked work and open private review artifacts.

Password authentication uses a salted PBKDF2-HMAC-SHA256 hash (600,000 iterations) and persistent sign-in rate limits. Session tokens are stored hashed on the VPS. Remembered sessions last 30 days; normal sessions last up to 12 hours and use tab session storage. Sign out revokes that browser session. The password is never stored in browser storage, Git or logs.

Initial setup requires a short-lived private invitation, cannot overwrite an existing password and disables the legacy dashboard key. There is no public password-reset endpoint; recovery requires owner-authorised VPS administration. The HTTPS endpoint uses sslip.io DNS and automatic certificate renewal. No ChatGPT, GitHub or SSH credential goes into the page or VPS.

Thesis jobs produce feasibility investigations, not complete theses. Current cards show the investigation decision, completed work and unresolved requirements directly. Project jobs continue through implementation, checks and deployment. A deployed prototype is not evidence of customer demand or production readiness.

## What you can use now

- [Public PR checkup](https://achkum.github.io/ai-project-lab/projects/rp1/): paste a public GitHub pull request URL; inspect older-revision approvals, possible conditions and failed/pending current-head checks; follow source links and download findings. Read-only requests go to GitHub, with no token. It does not verify branch rules or authorize merging. Endpoint reference: [GitHub review API](https://docs.github.com/en/rest/pulls/reviews).
- [Next-day preparation planner](https://achkum.github.io/ai-project-lab/projects/rp2/#planning): load daily sales for one item, set quantity and cost assumptions, calculate a next-day preparation quantity, compare historical excess/shortfalls against fixed daily preparation and download the plan. Start with the sample above the planning section. Rules only; no trained model or measured customer savings. Sold quantities can understate demand during stockouts.
- [Thesis findings](https://achkum.github.io/ai-project-lab/#thesis): RT1 is a small-pilot possibility with data/annotation gaps; RT2 is no-go in its original scope. Neither has experimental results.

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


## Working browser apps

- [Review evidence checkup](https://achkum.github.io/ai-project-lab/projects/rp1/): import normalized review-event JSON, inspect findings and timelines, export a report.
- [Forecast pilot](https://achkum.github.io/ai-project-lab/projects/rp2/): import consecutive daily CSV observations, compare rolling baselines, explore the chart and export a report. No pretrained model is evaluated in this slice.

Both process imported data locally in the browser and include labelled synthetic samples. These are usable prototypes, not validated commercial releases. Selected project builds proceed through automated checks and Pages deployment without a second approval gate.
