# Prata content contract 2026-11-01.9

This release corrects the meanings and responses of the guided exercises. It does not qualify a language model, establish broad free-response comprehension, or validate learner assessment. All 54 missions, 294 nodes, 456 intent edges, objective IDs and completion objectives remain stable.

The reviewed source SHA-256 is `c8142f993e390f90234d651c515e0d1c708bf78070e8361d2039b133c0ceb3e8`. The stripped semantic contract SHA-256 is `06eca18b84a8412e1b927a46def3d9ef9df4934ed17afd15acffd88e54ffec57`. The final stripped contract is byte-identical to candidate2, against which independent acceptance reconciliation was frozen. No hidden acceptance cases or candidate model outputs were accessed by the content author.

## Semantic corrections

All 108 final decline nodes now have meanings authored from the actual preceding offer. A specific illustrative answer no longer defines the canonical predicate. Refusing card payment does not require cash, refusing a chair does not require another seat, and refusing a loan does not require browsing. Neutral negative responses preserve earlier agreements without inventing a reason, alternative, later plan or cancellation outside the current offer.

Explicit current-offer refusal, clearly incompatible preferences or inability, and clear decisions to defer the offered action for now can express refusal. Mere uncertainty does not. A request for assistance alone does not refuse counter collection or travel to another bus stop, because those offers did not require doing so unaided. A clear answer may remain valid with harmless additional content; an unrelated-object denial does not automatically refuse the current offer.

Name verification separately permits denial of the stated name or an explicit refusal to verify it. Not knowing whether the name is right is neither of those acts. Generic willingness or suitability phrases were removed from automatic name-verification acceptance where their meaning was underdetermined.

Four affirmative meeting-time meanings no longer add an unstated key or tool handover promise. Both day-before notification nodes in `lib_shared_home_m2` permit oral notice; the timing requirement remains. One choice question and its preceding authored reply now use channel-neutral wording. Hypothesis, partner-feedback and inquiry nodes explicitly permit the question or tentative contribution their task calls for. This metadata is descriptive and imposes no keyword rule.

The exact old/new Swedish and English predicates, actual offers, questions, authored responses, graph flags and session guards are recorded per mission/node/intent in `semantic_review/final-2026-11-01.9/compatibility-*.json`. Compared with .8, 114 intent predicates and 106 authored responses changed. Compared with .7, 131 predicates and 108 responses changed. Question and incoming-offer counts of two in the maps refer to two intent rows at one changed choice node, not two separate questions.

`expected-act-changes.json` reports speech-act metadata separately. `example-inventory-adjudication.json` separately records 54 removed exact-response contexts, two added explicit name-verification responses, and four changed canonical examples across eight intents. Exclusion from automatic acceptance is not a new UNKNOWN gold label. This release changes the matcher inventory; its matching fingerprint is not claimed to be unchanged.

## Historical sessions

The .7 and .8 snapshot bytes are unchanged. The live deployment was .7; .8 had not been deployed. This content release does not migrate any session or rewrite any learner reply, selected recovery meaning, assistant turn or evidence.

The maps identify two .7 final nodes whose recovery labels addressed a different proposition: `lib_clothes_m2/confirm_return` and `lib_social_plans_m1/confirm_nextweek`. The corrected meanings concern holding the trousers and making contact on Monday. Existing selections cannot silently be reinterpreted as those corrected offers. The changed shared-home choice wording also needs an explicit session policy. Root/backend owns the restart, resume or audited future-checking policy. Unchanged graph structure alone does not authorize reinterpretation of history.

## Development-data adjudication

The original 1,862-case `natural_reply_evaluation.json` and its results remain untouched. The versioned manifest `natural_reply_adjudication.v2.json` accounts for every case: 1,314 retained development-regression contexts, 440 quarantined contexts, and 108 scoped nonsense controls. No replacement gold labels were assigned by this transformation.

The quarantine includes 108 instances each of mechanically prepending “Nej” to an affirmative choice, “Ja, men nej.”, “Nej, men ja.” and “Ja, det passar inte.”, plus eight generic offer responses at name-verification nodes. These require contextual adjudication; they are not automatically positive, negative or UNKNOWN. The 108 nonsense controls repeat one distinct string and are not counted as diverse natural-language coverage. Retained contexts contain 572 distinct texts and retain historical labels, rather than gaining independent gold status.

`natural_reply_cases.py` now reproduces the historical inputs and verifies them against the original artifact before writing only versioned adjudicated outputs. Historical response inventories and reports remain historical artifacts; use the explicit adjudication manifests when preparing future data. Separately owned disclosed-data and private-acceptance reconciliations have their own provenance and freezes.

## Checks and limits

The library checks passed all 216 terminal paths, 456 canonical replies, 5,558 approved exact-response contexts, 2,952 reject-term checks and 162 historical regression cases. Eight additional semantic/provenance test groups cover all final offers, subtype examples, assistance boundaries, name verification, permitted question acts, graph preservation and quarantine conservation. Reversing every illustrative refusal-answer list leaves all 108 canonical refusal predicates and responses unchanged. The retained 1,314-case diagnostic matches its historical expected labels; it is not a new generalization result.

The initial semantic test run contained two test-authoring mistakes: an assertion quoted the wrong metadata wording, and one assertion used the general question-policy key instead of the hypothesis-specific key. The initial report is preserved; fixing those assertions required no content change. Candidate2 and the final source remain byte-identical throughout these checks.

The independent acceptance owner reviewed the complete stripped graph and reported no remaining semantic blocker. These source checks and that semantic review do not establish production model accuracy, physical-device usability, pronunciation, official SFI grades or learning efficacy. Existing partial curriculum mappings and evidence limitations remain unchanged.
