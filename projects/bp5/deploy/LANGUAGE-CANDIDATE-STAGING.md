# Experimental Linux language candidate staging

This is a preparation workflow, not a release or an authorization to run or
activate a container. No trained candidate, release manifest, or acceptance
result is included. Preserve the existing live app, data, proxy, queue and
backups. The root operator owns the VPS and decides whether there is enough
host headroom before starting any isolated candidate.

## Export after training stops

Use the trainer's isolated environment only after training has exited. Prepare
a private JSON input manifest with exactly `base_revision`, `base_files` and
`checkpoint_sha256`. The revision must be
`8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`; `base_files` maps each of
`config.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json`,
`special_tokens_map.json`, `spm.model` and `added_tokens.json` to its exact
lowercase SHA-256. The source model and tokenizer hashes are additionally checked
against the original author's published revision. `checkpoint_sha256` is the
operator-verified training checkpoint hash. Keep the manifest and model files
in private runtime storage, not product source. After training finishes,
`prepare_language_export_manifest.py --base-dir <pinned-snapshot> --checkpoint
<finished-checkpoint> --output <new-private-manifest>` can create that file
without overwriting an existing one; it checks the author-published model and
tokenizer hashes and detects changes during hashing.

Run `export_language_fp32.py --base-dir <pinned-snapshot> --checkpoint
<finished-checkpoint> --input-manifest <private-hash-manifest> --output-dir
<new-private-directory>`. It fails if the directory exists, input hashes do not
match, or trained parameter names, shapes, dtype or finiteness differ. It
reconstructs the full FP32 model offline, exports ONNX, and compares PyTorch and
ONNX on short and near-512-token synthetic inputs, including a late negation.
A failure leaves `.incomplete`; a success leaves an export receipt explicitly
marked **not qualified**. An export may require multiple GiB of local RAM and
has not yet been run for this candidate. No automatic quantization is applied.
The previous PyTorch dynamic-INT8 training path collapsed base separation; do
not treat a smaller artifact as equivalent. Any future compression is a new
candidate requiring separate full development parity and independent acceptance.

## Build one promotable image

Prepare a private Linux wheelhouse and fully pinned `language-linux.lock` with
hashes for every direct and transitive dependency. Confirm the base image exists
locally by immutable digest and uses a Python ABI compatible with the pinned
wheels. Build from `Dockerfile.language-candidate` with the exact candidate
source, `--network=none`, `--pull=false`, and `--build-arg
BASE_IMAGE=<locally-present-image-digest>`. The wheelhouse/lock are build inputs
outside the product repository. Pip runs `--no-index --require-hashes` and
checks dependency versions. The image copies the actual production adapter;
there is no test-only inference implementation. Record the resulting immutable
image ID and never replace it between evaluation and any later promotion.

Before starting a service, run the image's `language_runtime_inventory.py` in a
separate disposable, networkless container and retain its sanitized hashes and
native-library inventory privately. Populate the private read-only artifact
root with the exact model, tokenizer, detector and runtime bytes specified by
an operator-reviewed candidate manifest. The child checks its actual loaded
Python, ONNX Runtime, tokenizer, NumPy and fastText binaries against the
manifest. Independently bind all other loaded libraries and the immutable image
identity in the Linux acceptance proof. Run `language_runtime_parity.py
--artifact-dir <read-only-export-directory>` in a separate container to compare
the export's synthetic token vectors with the actual image tokenizer. Neither
check establishes learner accuracy.

## Resource measurement with no public route

Only after all input/manifest hashes are known, and after checking the live
service and host have sufficient spare RAM and CPU, the operator may create a
**new** staging container with a unique name, a new empty private data directory,
and no network (`--network none`). Do not attach the live data volume, expose a
port, use host networking, restart another service, or change the public proxy.
Use the same immutable image intended for evaluation, a read-only root,
read-only model/manifest mounts, dropped capabilities, no-new-privileges and a
PID limit. Start with `--memory=1536m --memory-swap=1536m --cpus=1.8`; do not
silently increase this cap. If it fails, retain the failure/peak/OOM evidence
and let the root operator decide whether another bounded measurement fits the
4 GB host alongside the live service.

Configure the private container's own service for `HOST=127.0.0.1`,
`PORT=8788`, `LAB_DATA_DIR=/data`, `BP5_PUBLIC_ORIGIN=http://127.0.0.1:8788`,
`BP5_ALLOWED_HOSTS=127.0.0.1:8788`, `BP5_SEMANTIC_REQUIRED=1`, the
operator-bound `BP5_LANGUAGE_ARTIFACT_ROOT`, and the same read-only Piper,
Whisper and language artifacts required by the candidate. Create a random
non-secret staging marker only in the new data directory as
`/data/.bp5-isolated-language-staging`. Run `language_resource_probe.py` via
`docker exec` inside that container with `BP5_STAGING_PROBE=1`,
`BP5_STAGING_PROBE_TOKEN` equal to that marker, and
`BP5_STAGING_EXPECTED_MEMORY_BYTES=1610612736`. The probe refuses to run
without the marker, loopback-only origin and cgroup v2 memory/CPU caps. It
creates and deletes only its own disposable invitation/account, drives one
semantic turn alongside a synthetic Piper→ffmpeg→Whisper request, and reports
sanitized cgroup memory current/peak, OOM counters and timings. Keep the host's
container exit/OOM status, CPU quota, image ID, and artifact hashes with that
receipt; an OOM or missing metric is a failure, not a passing result.

This measures co-resident and overlapping single-user resource demand, not
throughput, learner speech accuracy, physical devices, or language quality.
The independent acceptance gate must evaluate the actual Linux candidate image
and exact runtime artifacts before any release. No staging action is automated
by this document.

## Image identity and native dependencies

`language_image_receipt.py` is a host-side, read-only container-inspection and
probe wrapper. Supply the full container ID and the **actual immutable image
ID** (`sha256:...`), not a tag. It checks the same running container/image and
restricted mounts before and after its `docker exec` probe and emits a combined
receipt. Set the staging token in the host environment; it is passed by name,
not printed. Store the receipt privately and bind its image ID, manifest hash,
probe hash and native-library inventory to the independent Linux acceptance
report and later promotion. Re-inspect the production container image ID and
read-only mounts at activation; any difference invalidates qualification. OCI
image identity covers its packaged filesystem and transitive dependencies, not
external mounts or the host kernel. Independently bind model, tokenizer,
detector and external runtime artifact hashes and enforce immutable read-only
mounts. The probe inventories actual worker-mapped `.so` paths and bytes after
ONNX load, but this is observational evidence, not a runtime loader policy; it
does not prove mappings cannot change after the snapshot. Qualification and
promotion must enforce the immutable image externally, without putting an
image's own digest inside the image and creating a circular hash.

The resource probe reaches an authored multi-intent step, constructs a
non-truncated 490–512-token synthetic reply ending in negation, kills the
single identified staging worker, verifies supervised restart, waits for the
normal per-account inference budget, and overlaps the real semantic HTTP turn
with synthetic transcription. It fails if the multi-intent case, restart,
overlap, or any other check cannot be observed. Its token counts are computed
from the pinned image tokenizer; learner accuracy is not evaluated.

The four-layer coverage checkpoint does not itself declare the training
objective or full trainable inventory. Export checks its exact known settings
signature and every tensor name/shape/type, but these cannot prove training
provenance: bind the trainer's separately signed/hashed objective and source
receipt before qualification. No lossless embedding rewrite is included; it
would be a distinct candidate requiring a separately audited graph transform
and full parity and acceptance, with memory gain actually measured.
