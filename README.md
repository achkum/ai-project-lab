# AI project lab

Public monorepo for continuous project delivery and a static dashboard spanning two lanes. Private companion: ai-thesis-lab.

## Current state
Dashboard shell implemented. Collectors, AI workers, VPS scheduling, authenticated commands and live export are not implemented. Example opportunities are illustrative, not research findings.

## Dashboard
Open docs/index.html locally, or serve docs with a static HTTP server. GitHub Pages publishes docs from main. No build dependencies.
data/status.json loads over HTTP; local file previews use sample.js. Profile export downloads a local draft and does not change VPS settings.

## Publish
Settings > Pages > Deploy from a branch > main > /docs > Save.
If a future exporter uses Actions GITHUB_TOKEN to commit status, add an explicit Pages Actions workflow; do not assume those pushes trigger branch Pages builds. A scoped VPS credential or GitHub App can publish allowlisted snapshots. No browser credentials.

## Layout
docs/: public dashboard only.
projects/<slug>/: each project owns its dependencies, tests and release materials.
config/: non-sensitive example profiles.
Unpublished ideas, evidence, logs and secrets: private VPS storage.

## Handoff
Read proposal.html and AGENT_HANDOFF.txt in private ai-thesis-lab. Implement one real end-to-end slice at a time. Preserve explicit setup and sample states.
