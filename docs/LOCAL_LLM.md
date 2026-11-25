# Built-in CPU GGUF translation

The `LOCAL_LLM` provider performs inference inside this Android application. It is separate from `OPENAI_COMPATIBLE`, which sends requests to an independently running server. No GGUF model is bundled. Import a compatible instruction model with the system document picker, select it, and choose the built-in provider. Loading and translating do not use the network.

## Independent implementation and source provenance

The new `local/` Kotlin code, `GgufBackend`, `local_jni.cpp`, and CMake project do not link to the previous Android application, its JNI, or its binaries. CMake builds the official llama.cpp C API from source:

* Repository: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp).
* Pinned commit: `f3269ef96aee8c9ec8a3a89a14025e33641827e3`.
* Archive: `https://codeload.github.com/ggml-org/llama.cpp/tar.gz/f3269ef96aee8c9ec8a3a89a14025e33641827e3`.
* Archive SHA-256: `97bfa08f20a45c4418440bb3ac83365628759a597bad213e96cd4a97bb94ec36`.
* Official references: [Android builds](https://github.com/ggml-org/llama.cpp/blob/f3269ef96aee8c9ec8a3a89a14025e33641827e3/docs/android.md), [C API header](https://github.com/ggml-org/llama.cpp/blob/f3269ef96aee8c9ec8a3a89a14025e33641827e3/include/llama.h), [GGUF specification](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md).

NDK `27.2.12479018`, CMake `3.22.1`, C++17, and Android API26 are configured. Production targets ARM64. The optional x86_64 build is for emulator verification. The source is built with portable CPU instructions, without host-native tuning, OpenMP, llamafile, OpenSSL, Vulkan, CUDA, Metal, BLAS or downloaded accelerator libraries. Native linking requests 16KiB page alignment. CMake limits compilation to four jobs and linking to one. A cached copy of the same source archive can be supplied with `CLICKN_LLAMA_ARCHIVE`; its SHA-256 is still checked.

## Resource and lifecycle limits

* SAF accepts `content://` streams only. Data is copied with cancellation checks and a fixed buffer; both advertised and actual sizes are bounded to 2GiB. GGUF magic, little-endian version2/3 and bounded tensor/metadata counts are checked before native loading. These admission checks do not establish model architecture compatibility.
* Imported models use their computed SHA-256 as the private filename. A temporary file is atomically renamed only after the full copy and validation. Display names are metadata, never filesystem paths. Credentials are not involved in local inference.
* One process-wide model/context is allowed. A coroutine mutex serializes loading, inference and unloading; work runs away from the UI thread. Context is512–4096 tokens, CPU threads1–8, and generation is32–1024 tokens. The output allowance must be smaller than the context.
* Native model loading uses a progress callback. CPU decoding uses the official abort callback and checks cancellation between batches/tokens. Kotlin signals abort, waits for the actual native call to finish, and only then releases the mutex or frees the session. A cancelled result is never returned.
* Normal translation rejects incomplete output when the token quota is exhausted. It never silently displays a truncated translation. Long paragraphs are split under the existing sentence-aware UTF-8 budget and glossary markers remain protected.
* Loading a new model/context closes the old one. The UI supports load, unload and delete. Deleting a loaded model unloads it before removing the private model files.

Model weights, working buffers, and KV memory still require substantial device RAM. The2GiB file limit is an import limit, not a promise that every permitted model fits every phone. A system process kill under memory pressure cannot be handled as an ordinary inference error. CPU speed, supported languages, translation fidelity and instruction following depend on the imported model. Models without a supported chat template are rejected for translation. This implementation does not supply GPU acceleration or promise parity with specialized MT.

The translation system prompt is customizable through `translationPrompt` with `{source}` and `{target}` substitutions. Source text is placed in a separate user chat message. The model's own supported chat template formats the messages. Native diagnostic logging is disabled; errors do not contain the source text or system prompt.

## Reproducible opt-in fixtures

The official tiny test model is only an inference smoke fixture; it is **not** a translation model:

* [ggml-org/models stories260K.gguf](https://huggingface.co/ggml-org/models/blob/499bc8821c6b12b4e53c5bffcb21ec206f212d81/tinyllamas/stories260K.gguf).
* Size1,185,376 bytes; SHA-256 `270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d`.
* Debug fixture cache filename `local-smoke.gguf`; instrumentation flag `runNativeLlmTests=true`.

A separate multilingual instruction model exercises actual English-to-Russian translation:

* [Official Qwen2.5-0.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/9217f5db79a29953eb74d5343926648285ec7e67).
* File `qwen2.5-0.5b-instruct-q4_k_m.gguf`, size491,400,032 bytes.
* SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
* Debug fixture cache filename `local-multilingual.gguf`; instrumentation flag `runLocalModelTranslationTests=true`.

`LocalLlmOptInTest` imports the exact fixture through a private debug content provider, verifies its digest, loads it, generates real native tokens or performs the translation, and unloads it. The multilingual test also cancels a live request and checks that native work has drained. It deletes newly imported model files afterwards. There are no network calls or model downloads inside these tests; the named independently verified fixtures must be supplied first. The fixture provider is excluded from release builds.

Builds and device runs must be reported separately from these test definitions. The ARM64 native source target compiled successfully. Its first API35 emulator attempt used an x86_64 device running ARM64 through Android's native bridge and crashed before model loading: `libndk_translation.so`, `ConvertF32F16`, called from `ggml_cpu_init`. Disassembly confirms the caller uses the baseline AArch64 `fcvt h0, s0` instruction; the compiler target is `aarch64-none-linux-android26` without an elevated `-march`. This result does **not** verify physical ARM64 execution. The app now rejects that known ARM64-on-x86_64 bridge with a managed error before loading JNI, and instrumentation separately checks the safe rejection. Native x86_64 QA builds and physical ARM64 devices remain enabled.

## Recorded verification, 25 October 2026

Implementation `5a6c355` passed actual native x86_64 instrumentation on Android8/API26 and Android16/API36. The separate API26 native run completed seven cases in21.745seconds: six real native passes and one inapplicable ARM-bridge guard skip. It verified exact fixture import/digest, loading, actual token generation, English-to-Russian greeting translation, live generation cancellation, cancellation before/after allocation, cancellation during a real llama.cpp load callback, and UI responsiveness while destruction was paused. Both complete Android suites finished65cases with63passes/two skips; logs and checksums are under [qa/wave2](qa/wave2/validation.json).

The first multilingual attempts returned the English source unchanged. An independently compiled, unmodified official `examples/simple/simple.cpp` from the pinned archive reproduced that output with the identical model and system-only task. Putting the task in the user turn with a separate source block produced a Russian greeting in the official oracle and the Android integration. `LocalChatPrompt` now uses that general framing; it does not rewrite generated output or special-case a source sentence. Custom system instructions and glossary-marker validation remain supported.

The0.5B fixture still showed weak instruction following, mixed-language output on a longer sentence and unreliable marker handling in additional host experiments. Passing the greeting proves the inference path, **not general translation quality**. The application rejects corrupted glossary markers and incomplete token-limited output; model selection remains the user's responsibility.

Debug native compilation retains symbols and uses an explicit `-O2` directory option: the recorded x86 build had76/76native compile commands with `-O2`, with no AVX2. SSE4.2 is enabled only for the optional x86_64 build because it is part of [Android's x86_64 ABI baseline](https://developer.android.com/ndk/guides/abis); optional AVX/FMA/F16C remain disabled. Production ARM64 uses the Android toolchain's release optimization. Physical ARM64 GGUF inference remains unverified; ARM-on-x86 bridge rejection is separate evidence.
