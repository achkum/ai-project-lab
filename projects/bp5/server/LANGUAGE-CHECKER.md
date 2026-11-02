# Experimental language checker infrastructure

This code is infrastructure only. No model or thresholds are approved, the
module-level adapter remains unavailable without a qualified operator manifest and artifact root. Enabling `BP5_SEMANTIC_REQUIRED=1` without them makes `/ready` and semantic turns fail closed. No project manifest is shipped.

`language_checker.Checker` can be instantiated explicitly by local tests with
absolute model/tokenizer paths, their SHA-256 hashes, revision, calibrated
probability threshold and margin, and bounded thread/token limits. It uses
`language_process.WorkerSupervisor` to start `language_worker.py` with the same
Python interpreter. Dependencies for a future isolated inference environment
are listed in `requirements-language.txt`; availability and reproducibility on
the target Linux image must be verified separately.

The parent verifies model, tokenizer, language detector, Swedish vocabulary, and vocabulary-source SHA-256 values; the child independently verifies the model, tokenizer, and language detector. The child's
initialization handshake occurs only after the ONNX model loads and its input
and output signature is checked. Requests and replies are bounded JSON lines;
one of the request text or generated interpretations is logged. A deadline or
protocol error kills the worker process tree and waits for it to exit before
releasing the single admission slot. Linux process groups and Windows
`taskkill /T` cover normal descendants; deployment should also use its own
container or cgroup process and resource limits. A blocked slot returns busy
rather than building a queue.

The current experimental pair format mirrors the trainer pilot: premise
`Fråga: {question} Svar: {reply}` and hypothesis `Svaret betyder: {meaning_sv}`.
The tokenizer does not truncate; a request exceeding the configured token
limit fails as unavailable rather than losing a trailing negation. An optional
explicit context resolver can supply the actual offer from a frozen graph and
recent turns. The pilot does not yet use graph history. No correctness or
language-coverage claim follows from this format.

`choose()` is a pure scores-to-decision function. Unknown means the configured
threshold or margin was not met; unavailable means inference, context,
artifacts, or bounds failed and must not mutate a turn. The local language-support gate combines the raw fastText detector signal with a source-bound Swedish vocabulary for short replies. It is coarse, not proof of proficiency or intent, and must be evaluated for false positives and false negatives. Shared confirmations are handled only in a confirmation step. Detector label and combined support decision are recorded separately. The full fastText language model is licensed CC-BY-SA 3.0; review attribution and redistribution requirements before shipping.

The development detector is the full `lid.176.bin` from
[fastText language identification](https://fasttext.cc/docs/en/language-identification.html),
SHA-256 `7e69ec5451bc261cc7844e49e4792a85d7f09c06789ec800fc4a44aec362764e`.
Its model is distributed under CC-BY-SA 3.0. It remains outside product source.
`swedish_support_vocabulary.json` is generated only from the authored Swedish
fields by `build_swedish_support.py`; its embedded library hash is verified.
Any library change requires regenerating and revalidating this artifact. Raw
fastText language, combined support, and support evidence are separate trace
fields; lexical support never selects an intent. On one development set, this
policy still blocked 37 valid Swedish contexts; it is not independently
validated and must not be represented as comprehensive language detection.

A future candidate must pin the worker, prompt/context configuration, language
policy, calibrated thresholds, runtime dependencies, and exact artifact hashes
in the release gate. It must pass independent language and security tests in
the actual Linux candidate runtime before deployment. Never use development
fixture scores as acceptance evidence.

## Candidate binding contract

Only an operator can configure `BP5_LANGUAGE_ARTIFACT_ROOT`; the manifest is
always `LANGUAGE_CHECKER_MANIFEST.json` at the project root and cannot be
supplied by a request. Each `artifacts` entry contains only a safe root-relative
`path` and a SHA-256. Symlinks, junctions, path traversal and changed artifacts
are rejected. The adapter declaration must identify `server/language_checker.py:check`,
`production_adapter`, the Linux runtime and the independently evaluated Linux
target. Its environment binds `BP5_SEMANTIC_REQUIRED=1` plus the exact
`BP5_SEMANTIC_BURST_UNITS`, `BP5_SEMANTIC_REFILL_UNITS_PER_MINUTE` and
`BP5_SEMANTIC_COOLDOWN_PERCENT` values used by the process.

Configuration fields are `model`, `tokenizer`, `language_model`, and
`runtime_artifacts` (relative paths with `python`, `onnxruntime`, `tokenizers`,
`numpy`, `fasttext` roles); `library_sha256`, `library_version`,
`vocabulary_sha256`, `checkpoint_id`, `base_model_revision`, `tokenizer_revision`,
`calibration_source`, `threshold`, `margin`, `max_tokens`, `threads`,
`timeout_seconds`, `startup_timeout_seconds`, `label_mapping`, `premise_format`,
`hypothesis_format`, and `language_policy`. All artifact roles must be distinct
and listed with hashes. `max_tokens` is 512; labels are entailment 0, neutral 1,
contradiction 2; format IDs are `offer-question-reply-v1`, `meaning-sv-v1`, and
`fasttext-vocab-v1`. Runtime native binaries are also rehashed by the child
after import; container identity and all linked dependencies still require
independent Linux release-gate verification.

The bound premise is `Erbjudande: {offer}\nFråga: {prompt}\nSvar: {reply}`.
The offer comes from `language_context.current_offer`; unresolved context yields
unknown without inference. Optional evaluator-only tracing returns input
character count/hash, per-pair token counts, and truncation status. Production
turn records do not retain that fingerprint. A token overflow returns an
actionable 413 and does not mutate the mission.
