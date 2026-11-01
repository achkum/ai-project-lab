# BP5 content contract, 1.0

`scenarios.json` and `curriculum.json` are UTF-8 objects with `schema_version` and `content_version`. Use stable IDs, not array indexes. Optional future fields may be added; do not infer a course from a scene's challenge level.

Scenarios are under `scenarios`. Each has a character, Swedish opening and English help, objective list, phrase cards, support objects, dialogue guidance, an audio-only listening check, connected reading and writing, retry coaching and later recall/transfer. The high scene targets several speaking minutes; turns and time are not assessment scores. Reading and listening use different messages to reduce answer leakage.

`criterion_links` points into `curriculum.criteria` by `criterion_id`, with its `framework_id`, activity and partial-coverage limitation. Supported activity IDs: `dialogue`, `dialogue_summary`, `listening`, `reading`, `writing`, `writing_copy_extension`. The copy extension is a distinct current-A writing opportunity; do not map a composed message to it. Activities with no matching selected-course link remain unmapped.

Frameworks carry course arrays (`id`, `label`, `study_paths`, `course_codes`) and domain arrays (`id`, `label`). Current A–D criteria are shared across the allowed study paths; new 1A–3D retain separate course identifiers even where criterion wording is alike. Criteria expose a concise English summary and exact source URL, printed PDF page(s), course and section. Full official text controls. Every task mapping is partial and awaits educator review.

Save framework, course, study path, criterion, source and content version with each observation. Keep unknown fields explicitly null. Do not migrate historical observations when a profile changes. Today’s date is insufficient to choose a framework. The 2026:67 commencement and transitional provisions, printed pages 1–2, distinguish effective date, applicability to education and continuation for earlier courses.

Completing a task may save `practised`. `observed_with_help` and `observed_independently` require a reviewed specific successful action, evidence and reviewer type. No keyword match, turn count or self-reported session completion establishes a criterion. The latter state means this attempt lacked task-specific help; it is not mastery. Keep any learner self-review labelled as self-review. Do not derive official results or scores.

Hide listening source text and answer ideas until the learner responds. If exposed, listening stays unassessed. Dictation is not independent writing. Typed chat is not speaking. Corrected speech transcripts may describe limited content, never pronunciation or fluency. Record hints, translation, replay, notes, text visibility and input provenance. Unknown provenance cannot count as independent evidence.

All scenario text is original fictional material. Feelings are optional learner-selected context, with a fictional alternative. Memory benefit is a hypothesis requiring delayed recall and transfer evaluation. No national test items are included.

Rebuild with `python content/build_content.py`; validate with `python content/validate_content.py` from the BP5 project directory. Validation checks data integrity and evidence boundaries, not pedagogical accuracy or learner ability.
