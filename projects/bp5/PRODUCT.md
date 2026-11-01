# The working customer workflow

An adult learning Swedish needs repeated, understandable practice before real daily interactions. One coffee example is not enough: the app needs different tasks, help, a clear next exercise and a history that survives closing the browser.

Prata supplies 54 guided tasks across 18 situations, spanning short requests, conversations with familiar people and longer structured problem discussions. A learner creates a private account, chooses a task, speaks or types, reviews speech recognition, receives an authored reply, completes connected reading/listening/writing practice, saves phrases and continues to another task. They can return later, export/delete data and recover account access.

When the app does not recognize a reply, the learner can choose the intended meaning and continue without replacing the original sentence. That choice is recorded as supported practice, never automatic understanding or a language grade. Editable response examples are another optional aid. Saved follow-up answers remain visible; reading/listening provide authored comparison ideas after the attempt.

The app runs independently on the existing VPS with no new paid API/cloud service. Small speech models handle transcription and Swedish audio; deterministic matching controls authored conversation. It does not call a general language model or require customer API keys.

Acceptance requires real account isolation, durable sessions and recovery, a different next Basic task, a complete path through every mission, honest source/version-aware SFI evidence, speech cancellation and retry, supported mobile recording formats, HTTPS delivery, restart persistence, recoverable deployment and encrypted backup restoration. Unit fixtures, synthetic speech, public human-read audio, actual browser behavior and physical-phone testing are separate evidence categories.

Current boundaries: invitation-only access; one simultaneous speech job; 200 stored practice sessions per account; guided, limited language recognition; imperfect transcription; partial SFI mappings without official grades. The library is not a full SFI course. Educator review, real learner-accent/mobile-microphone trials, accessibility user studies and evidence of improved learning are not established by automated checks.

The recognition limitation is measured, not merely hypothetical: after repair, a fresh independent diagnostic accepted only 2 of 18 valid paraphrases and rejected all 18 negative/uncertain replies. Perfect scores on the disclosed regression corpus did not generalize. Two small semantic-model fallbacks also made false acceptances and were not deployed. Explicit meaning confirmation supplies recovery for guided practice; it does not establish broad natural-language understanding. See `content/language_quality_report.json` for the dated evidence.

The business hypothesis is repeated practice that learners find useful enough to return to or pay for. That hypothesis remains unvalidated. The implementation is a usable foundation for invited customer testing, not proof of demand, learning effectiveness or profitability.
