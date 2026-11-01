# Runtime provenance and notices

These are implementation dependencies and background references, not claims of new market demand or research novelty. Model weights and binaries are not committed to this repository.

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp), v1.9.5: MIT. The Docker build pins the source archive SHA-256.
- [KBLab KB-Whisper Base](https://huggingface.co/KBLab/kb-whisper-base): Apache-2.0. Swedish-specific pretrained transcription model; the deployed quantized file is pinned by revision and hash in the operator runtime manifest. [KB-Whisper Small](https://huggingface.co/KBLab/kb-whisper-small) was evaluated separately; evaluation does not mean deployment.
- [KBLab Swedish NST Piper voice](https://huggingface.co/KBLab/piper-tts-nst-swedish): original model card states CC0. The installed ONNX archive is the original publisher-linked `voice-sv-se-nst-medium.tar.gz`, linked in the [24 May 2023 publisher article](https://kb-labb.github.io/posts/2023-05-24-swedish-text-to-speech/). Pronunciation/prosody can be imperfect.
- [Piper](https://github.com/rhasspy/piper), Linux release 2023.11.14-2: MIT engine. Bundled eSpeak NG has its own GPL terms; preserve bundled notices and comply with applicable source obligations when redistributing binaries/images.
- [FFmpeg](https://ffmpeg.org/legal.html): Debian's package includes components with GPL/LGPL terms. The app uses the installed command-line executable. Preserve package copyright/source information when distributing an image.
- [age](https://github.com/FiloSottile/age), v1.3.2: BSD-3-Clause. Backup encryption runs on the host. Only its public recipient is kept on the VPS; the recovery identity is private on the owner's laptop.
- [Google FLEURS](https://huggingface.co/datasets/google/fleurs), Swedish test split: CC-BY-4.0. Six public human-read clips were used for a small engineering check. They are not learner speech, not used for training, and not shipped in the application. The evaluation record contains exact revision and clip hashes.
- Python service dependencies are pinned in `server/requirements.txt`; installed package metadata retains their respective licences.

Official SFI source links and version dates are retained in `content/curriculum.json` and the library provenance files. Author-written scenes are interpretations for practice, not official SFI examination material.
