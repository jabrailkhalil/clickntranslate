# Component updates

Components are published separately at https://github.com/jabrailkhalil/clickntranslate-components.
Application releases and their `/releases/latest` feed are unchanged.

## Current rollout

The first published managed profile is Windows x64 CPython 3.12 + RapidOCR 3.10.0 with explicit PP-OCRv5 models. It is **preview**: the source application and standalone runtime are tested, but a frozen application with the new client has not been built. The stable channel deliberately has no approved profile yet. Windows Tesseract 5.5.3, Argos 1.11.0 and native Hy-MT are integrated with the store and tested as **local candidates**, not public catalog approvals. macOS/Linux retain their existing installation paths until their managed profiles pass native validation. EasyOCR has not been migrated to the new store. Android needs its own installer and executable-code policy.

Select preview only for local QA with `CLICKNTRANSLATE_COMPONENT_CHANNEL=preview`. Isolate QA files with `CLICKNTRANSLATE_COMPONENTS_DIR`; this is separate from the user's normal engine directory. No unsigned catalog fallback or on-the-fly dependency resolution is permitted in the managed Windows RapidOCR flow.

## Native Tesseract candidate

- A native bundle uses `runtime: native` and an executable path, without a Python interpreter. Optional `language_files` are materialized for the selected language set before staging. The receipt records the actual installed set, not every language the engine supports.
- Adding/removing languages creates a generation even when the engine bundle id is unchanged. Updates preserve the selected languages, including an intentionally empty set. Unchanged files use the verified object cache. A previous language set can be rolled back along with its engine.
- Portable/system legacy installations remain intact during migration. If a custom installed model is not covered by the approved catalog, migration stops rather than silently dropping it. The `osd` orientation model is not advertised as a recognition language.
- OCR and fullscreen layout calls pass native argv entries and a generation-specific data directory. They do not rely on pytesseract's Windows config-string quoting or a mutable global `TESSDATA_PREFIX`. Active OCR holds a shared generation lease.
- `tools/prepare_tesseract_component.py` prepares a candidate from a pinned, extracted upstream installer and tessdata_fast commit. The NSIS installer is never executed. Source-archive aliases such as `frk` are excluded; the canonical `deu_latf` model is available.
- `tools/qa_tesseract_components.py` tests actual native OCR, language selection, reuse, rollback, and rejection of invalid traineddata in an explicitly isolated QA directory. It uses real pinned HTTPS model URLs; the unpublished runtime candidate is copied locally.
- Publishing the repackaged Windows runtime additionally requires a complete license/source inventory for its bundled third-party DLLs. Candidate preparation deliberately records `redistribution_review: false` and does not publish it. No stable or public Tesseract profile is implied by source-mode success.

## Client

- `component_catalog.py` authenticates metadata using `python-tuf`, then validates and selects compatible descriptions.
- Entries with a newer adapter contract are ignored by older clients, so adding a future engine adapter does not block updates for their compatible existing engines. A new layout must use a new contract instead of changing an existing contract in place.
- `component_store.py` keeps verified objects and installed generations, with a SQLite activation journal and interprocess locks.
- `component_runtime.py` starts the selected interpreter/adapter in an isolated process. OCR never needs to import ONNX/OpenCV in Qt.
- An update stages a complete new generation and performs real inference before committing its active pointer. One previous generation is retained.
- Unchanged artifacts are checked and reused. A worker holds a generation lease so removal/cleanup cannot delete its runtime. Pending cleanup completes when that worker releases its lease.
- Large artifacts resume with HTTP Range/If-Range, bounded retries, cancellation and approved size limits. A server ignoring Range restarts the file. Malformed ranges restart instead of appending inconsistent bytes. A full SHA-256 check is required before extraction or activation.
- Removing selected languages/directions is an offline transaction reconstructed only from the current authenticated receipt and verified object cache. It cannot add files or change the engine version. Cached catalog rows are for presentation; installation still authenticates a fresh catalog.
- Rollback requires an approved, non-revoked previous bundle in a trusted catalog; rollback never resets TUF trust state.
- Corrupted/expired/unreachable update data cannot replace a working generation. Already installed offline OCR does not require a network refresh.
- Files and receipts are flushed before activation. Recovery removes uncommitted candidates. Filesystem/hardware durability still depends on the operating system; absolute power-loss guarantees cannot be inferred from process-crash tests.

## Argos and native-runtime candidates

- The initial Argos candidate has four pinned original model archives: EN→RU, RU→EN, EN→AR and AR→EN. RU↔AR uses the installed English pivot. The candidate does not claim support for the entire upstream index; legacy installations remain unchanged until an explicit managed update.
- The SDK and CTranslate2 run in a private Python process, never in Qt. The existing dependency-free sentence splitter avoids installing Torch/Stanza/SpaCy. The worker forces local CPU inference and immutable package directories, regardless of inherited Argos cloud-provider settings.
- Adding a direction, updating the runtime and rolling back preserve the selected set. Every selected model performs real inference before activation. Cancellation kills and waits for the validator before removing its staging directory. Translation holds a generation lease, including while streaming chunks.
- `tools/prepare_msvc.py` extracts pinned CAB data from the official Microsoft redistributable without executing EXE/MSI installers or installing anything system-wide. Source/archive/individual DLL hashes are recorded. `tools/runtime_dlls.py` rejects missing private imports and incompatible bundled exports; `runtime_bootstrap.py` verifies the private MSVC DLL paths before importing native SDKs.
- Current prepared RapidOCR/Argos candidates fix reliance on the developer machine's global MSVC installation. The previously published RapidOCR preview is not silently overwritten. New artifact publication remains separate from preparation and requires redistribution review plus final-byte native validation. Source tests do not prove operation on a clean or frozen Windows application.
- Recipes preserve original licenses/notices. The Microsoft runtime description records `redistribution_review: false` until checked for publication. The Tesseract third-party DLL inventory is a separate gate.

## Publication

### Native Hy-MT candidate

- The profile pins the HY-MT1.5-1.8B Q4_K_M GGUF, its matching model documentation/license revision, and a Windows CPU llama.cpp runtime. Models and runner archives are separate objects, so updating llama.cpp does not download the 1.13 GB model again. Existing verified legacy models can seed the cache without changing the originals; custom models outside the approved plan stop automatic migration with a localized explanation.
- The initial candidate compares the existing b9048 runner with b11899 on the same model and EN/RU/AR samples, plus Chinese→Indonesian. This is an inference/lifecycle comparison, not an accuracy score or a clean/frozen Windows qualification.
- Managed inference passes UTF-8 prompt files to a native child, limits CPU threads, removes inherited LLAMA_ARG overrides and does not load a Python LLM SDK into Qt. Cancellation kills and waits for the child. A long request leases one generation across all its chunks; updating/removing another generation cannot break it midway.
- Translation cache identities include the approved runtime/model plan. Reinstalling identical bytes or rolling back can reuse their matching cache, while new bytes do not reuse output from an older model/runtime.
- Explicit managed removal leaves preserved legacy files intact but disables their automatic fallback, so an uninstall does not unexpectedly resurrect an old engine. Windows Install/Update uses the trusted profile; macOS/Linux retain their prior flows.
- `tools/prepare_hymt_component.py` selects the CLI's native dependencies and every upstream CPU backend, retains upstream notices, bundles the pinned Microsoft runtime and audits imports. `tools/qa_hymt_components.py` exercises actual update/rollback, cancellation, invalid GGUF rejection, offline removal and loaded private DLL paths. No new Hy-MT artifact is approved for the public catalog by these commands.

The component repository contains recipes, locks, publisher scripts, and public metadata. Runtime ZIPs are Release assets. Models currently retain pinned ModelScope URLs and SHA-256 rather than being silently selected by the library. Large future models may use other exact-revision sources.

The embedded `src/component_root.json` is the trust anchor. Root/targets private keys remain in the maintainer's private signing directory outside repositories. Only snapshot/timestamp role keys are configured as encrypted Actions secrets in the component repository. They can renew freshness but cannot approve a different catalog. Application signing identities are untouched.

Initial key material on the maintainer machine is under `~/.clickntranslate/component-signing/`. Back up those private files securely before a stable rollout; never commit or attach them to an issue. Root rotation must be authenticated by the previous root and tested against existing clients.

Prepare a runtime with `tools/prepare_component_runtime.py`, record exact wheel hashes, and test the final bytes on their native platform. `tools/component_catalog_recipe.py` describes prepared files; it does not approve them. `tools/component_repository.py` signs a maintainer-approved catalog. `tools/publish_components_github.py` performs explicit repository/release/Pages operations using the existing Git credential helper without logging credentials.

Signed targets must retain exact bytes across Windows/Linux checkouts. The component repository's `.gitattributes` disables line-ending conversion for `public/`. Models/archives are verified again after downloading. The daily Pages workflow renews online metadata only; offline approvals expire and require maintainer renewal. Discovery reports candidates, never promotes them automatically.

## Required next gate

Before promoting to stable: build a new application only when authorized, check the frozen client without developer Python, then exercise installed/portable paths and another controlled component revision. A source-mode success is not a frozen-app or macOS/Linux success. Component archives are not ClicknTranslate application releases.
