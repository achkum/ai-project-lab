# Prata — Swedish practice for real situations

An adult learning Swedish can rehearse a conversation before trying it in everyday life: order a coffee, ask a neighbour for help, or talk through a problem with a friend. Voice practice connects to a short reading/writing follow-up, saved phrases and later reuse. This is a responsive web app; no Android or iOS installation is required.

This private prototype uses local AI. **It can mishear speech and generate incorrect or unnatural Swedish.** Review the transcript before sending it. Coaching is experimental. SFI progress records practice evidence, support and source-linked goals; it is not an official grade or course placement. Educator review and human-speaker testing remain necessary before educational-effectiveness claims.

## Use

Choose a situation and difficulty, optionally select your actual SFI framework/course, then speak or type. Listen to the character, use help if needed and review any transcript edits. Continue to listening, reading and writing, save useful phrases and revisit them later. Progress lets you resume, export or delete practice. Difficulty settings do not correspond automatically to SFI courses.

The deployed private pilot uses the owner's existing lab password. The laptop runs inference and must remain on; the VPS provides the HTTPS access path. This is single-owner access, not a public multi-tenant learning service. No new paid API or cloud inference is used.

## Run locally

Use Python 3.14 and the separately installed runtime listed in [the runtime manifest](server/RUNTIME-MANIFEST.json). Model weights, binaries, recordings and databases are excluded from Git. See [backend setup and measurements](server/README.md).

Set `HOST=127.0.0.1`, `PORT`, `LAB_DATA_DIR` to a private data directory, `LAB_INSTANCE_ID`, and `BP5_RUNTIME` to the installed model directory. Start `python server/app.py` from this project. The default runtime path assumes this checkout remains under `ai-project-lab/projects/bp5`.

The selected local dialogue model's measured child-process peak was about 4.36 GiB; the service declares 5 GiB admission. This is not an OS memory limit or a promise of low latency. Model calls are serialized on this laptop.

## Check

Run `python -m unittest discover -s tests -p test*.py`, `node --test tests/*.test.cjs`, and `python content/validate_content.py` from this directory. Automated API tests use controlled inference fixtures for determinism; actual runtime measurements and end-to-end checks must be reported separately. Synthetic speech checks are not human-speaker accuracy validation.

Visual patterns come from the owner's Drift and SubTrack projects. Sources and versions for the SFI criteria are in `content/`. The current and January 2027 frameworks remain separate, including earlier-course continuation rules.
