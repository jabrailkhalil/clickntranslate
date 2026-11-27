# OCR lifetime and performance

The application keeps Python/Qt and the existing approved native engines. No
compiler, service, system interpreter, global package installation, or new
native dependency is required by these changes.

## Resource and compatibility contract

- Starting the app does not warm OCR engines or create unused capture overlays.
  Source-mode Argos also starts its private/native work only on demand.
- Repeated RapidOCR requests can reuse one loaded model. An explicit change of
  the installed OCR engine/source language can prepare just the selected
  RapidOCR model in a short-lived background coordinator. A tiny private image
  exercises the selected models; no screenshot, clipboard, network request or
  other language model is used. Opening settings, choosing an output language,
  and startup do not trigger preparation. Another language/generation replaces
  the retained model; an unrelated active model does not block a separate
  one-shot request.
- Dynamic OCR region/full-screen sessions own retention tokens: the model stays
  ready until the last active session pauses or stops. Five full idle minutes
  begin at that point. One-shot OCR expires five minutes after its last request;
  it is never periodically reloaded. Plain text/API documents do not pin OCR;
  the existing document-specific Argos worker already spans its document.
- Preparation is currently enabled for the verified resident RapidOCR adapter.
  Windows OCR/Tesseract/EasyOCR and older immutable component adapters keep
  their established compatible paths; they do not waste CPU warming and then
  immediately discarding a one-shot model.
- The OCR process exits after five idle minutes. Retention is rejected above
  384 MiB resident RAM or under reported system memory pressure. This is a
  retention budget, not a claim that inference peak memory is capped.
  While a model exists, a cheap memory-pressure snapshot every thirty seconds
  can retire even a pinned model. No memory monitor runs before OCR is used.
  Switching away from an unused engine, uninstall/reset and real app exit also
  retire it. Hiding the app to the tray does not count as exiting.
- Engine thread counts, model bytes, confidence thresholds, image preprocessing
  parameters and sampling/translation parameters are unchanged. Speed comes
  from removing repeated initialization, copying and rendering work.
- Cancellation kills and reaps an owned native child before removing its input
  files. A child owns the component generation lease for its full lifetime.
  Windows Job Objects cover application death; pipe closure also ends workers.
  Read-only resident children keep the OS lease until process exit, including
  shutdown of all native threads.
- A resident reader starts after the first actual native initialization on
  Windows (including explicit preparation). Starting it sooner deadlocked the private NumPy/OpenBLAS import in
  a real-model test; this ordering is covered by the native benchmark.
- Resident processing uses versioned bounded JSON/PNG messages. Unsupported
  host isolation falls back to the existing one-shot contract.
- Source previews on Windows can use the current application adapter with the
  installed **pinned** RapidOCR runtime's private Python. The approved component
  files are not changed. Unknown SDK versions retain their own adapter.
- Frozen apps and POSIX use the resident protocol only when their curated
  component declares it. Existing component downloads remain compatible.
  Recipes declare the adapter files and protocol for future approved packages;
  this change does not publish or replace those packages.

## Other changes

- Dynamic RapidOCR receives the selected source language, rather than defaulting
  to English.
- Frozen Linux dispatch uses an available bundled OCR worker instead of trying
  to import a runtime excluded from the GUI package.
- OCR line grouping caches bounds and skips finished baselines. Original
  geometry, tie-breaking and Latin reading order are retained; Arabic fragments
  use the existing logical reading-order helper.
- Dynamic overlays reuse their layout plan between mask and paint. Background
  palettes and the source QImage are cached only for the current frame.
- Full-screen pixel conversion runs in the OCR thread. The GUI transfers an
  implicitly shared owned QImage instead of converting full-frame pixels first.
- Dynamic translation reuses idle HTTP sessions. Workers start as needed and
  expire after inactivity; up to sixteen independent requests remain possible.
- LibreTranslate request and cache identity use the same captured connection.
  A server change cannot relabel an in-flight response. Document operations
  reuse their translation configuration context.
- Documents can send new completed parts to Qt instead of repeatedly copying
  the whole translated prefix. The first part is sent immediately; subsequent
  updates can coalesce. Existing cumulative callbacks remain supported.
- Adapters supporting document batches run one Argos process per document.
  Older installed adapters retain the previous compatible path. Chunk mapping
  and bounded delivery are checked before results are published or cached.
- Retired component deletion runs in coalesced maintenance work rather than
  delaying OCR result delivery. Generation locks and durable recovery remain.

## Recorded Windows checks, 2026-10-27

Real RapidOCR 3.10.0 / PP-OCRv5, same locally installed approved bytes in both
paths. Three one-shot calls and three demand calls per image (first demand
call cold, next two reused). This is a small comparison, not a reliable p99.

| Input | One-shot median | Reused median |
|---|---:|---:|
| English | 1201 ms | 255 ms |
| Russian | 1158 ms | 237 ms |
| Arabic | 1112 ms | 237 ms |
| User's game-book screenshot | 1227 ms | 239 ms |

Text, polygons, confidences and reading order matched exactly in the compared
outputs. All cases contained real text. Cold demand calls remained approximately
1.1–1.2 s. OCR timing excludes online translation and GUI presentation.

The retained process used approximately 115–122 MiB resident RAM in these
checks. The earlier ten-second-policy lifecycle checks recorded zero additional CPU time during a
steady one-second idle interval, automatic exit at 10.03 s, identical output
after restart, and cancellation/reaping in 78 ms. Native pools' initial
post-inference spin is excluded from the steady idle interval; this does not
claim zero CPU usage while recognizing text.

The current policy is five minutes, rather than the ten-second timeout used in
that earlier measurement. The final selected-model/lifetime run is recorded
separately under `.tmp/ocr-readiness-native-final/results.json`:

| Input | One-shot median | First OCR after background preparation | Reused median |
|---|---:|---:|---:|
| English | 1272 ms | 403 ms | 283 ms |
| Russian | 1570 ms | 608 ms | 316 ms |
| Arabic | 1309 ms | 436 ms | 359 ms |
| User's game-book screenshot | 1375 ms | 450 ms | 269 ms |

All compared outputs, including the first actual recognition after preparation,
matched the one-shot text, confidence and polygon coordinates exactly. The
five-minute process exited at 300.015 s; steady idle CPU delta was 0 s over the
one-second sample, restart output was identical, and cancellation/reaping took
78 ms. Explicit preparation in the lifecycle run took 1062 ms off the GUI;
its first real OCR took 438 ms and reused the prepared child. Retained RSS
across the corpus was about 115–125 MiB. These are small local measurements,
not a percentile or a promise under other CPU/memory loads.

An additional check through the actual `ocr.prepare_selected_ocr` and
`ocr._call_native_ocr_worker` application bridge verified a nonempty Arabic
result, reuse of the prepared child, activity ownership, and reaping on a switch
to Windows OCR (`.tmp/ocr-readiness-bridge-final/results.json`).

This native check caught a persistent RapidOCR option: `use_det=False` during
recognizer preparation remains set for later calls. The probe now restores the
original detector flag and exercises detection explicitly. Both fake-engine
regression and real prepared-result comparisons cover this failure.

The same offscreen grouping benchmark for 500 visual fragments improved from
130.4 ms to 1.65 ms. This is one operation, not an application-wide speedup.
Three hundred seeded layouts check equality against the previous algorithm;
RTL has separate reading-order tests. UI navigation/theme measurements did not
establish a material additional speedup and are not advertised as such.

## Reproduction and limits

Use `tools/run_regression_tests.py` with an isolated profile. Relevant coverage
includes demand startup, cancellation, generation leases, over-budget release,
Unicode/space paths, worker expiry/restart, document delta payloads, exact chunk
mapping, cache connection changes, and real Windows OCR pixel conversion.

`tools/benchmark_demand_ocr.py --component PATH --output PATH --lifecycle`
uses an existing component read-only. `--reference IMAGE` adds a local English
reference image. It opens no visible window and performs no download.

Raw local evidence is under `.tmp/performance-demand-native-final/results.json`
and `.tmp/performance-demand-qa/bench/measurements.json`. No model benchmark on
macOS/Linux, real Argos document benchmark, WAN/API latency result, or game frame
rate claim is made here. POSIX resident mode must pass native platform checks
before its component is published. No application build or release was made.

The broad isolated regression run passed 645 tests and 30 subtests; one monitor
coordinate check was skipped because that run used Qt offscreen. A subsequent
targeted lifecycle/lease/startup check passed 112 tests. These counts overlap;
they are not a sum of distinct test cases. User data hashes were unchanged.

For the selected-model policy, the final core group passed 331 tests and 24
subtests. Subsequent checks of the final startup/pause fix, actual dynamic Qt
controls and shutdown passed 73 tests and 24 subtests; these groups overlap.
Their isolated profiles reported unchanged user data. A combined offscreen GUI
run hit a native Qt access violation during a surface grab; the affected
dynamic workspace passed in the subsequent isolated run. A separate 171-test
GUI group passed its assertions, but its data guard noticed the concurrent
standalone native bridge appending diagnostic log lines. Config/history were
unchanged; this is not reported as a fully clean data-guard run.

## Engine center and live settings language, 2026-10-27

The five settings pages now translate their existing controls in place rather
than disposing and rebuilding the complete form. Saved selections, checked
result modes, tooltips and accessible descriptions are relabeled together.
Untouched default language pairs may still follow a new interface language;
customized pairs retain their IDs. Installation metadata is reused for a
language switch and refreshed after component or provider changes.

In a local Qt offscreen cProfile run, a language change fell from approximately
260 ms to 27–30 ms. This includes UI processing, not a native frame-time
percentile; it does not establish first-opening or theme-switch performance.
The first Settings construction remains a separate cost to measure.

The engine center keeps an explicit fixed baseline size through its OCR,
translator and API pages. Its action buttons have parents from construction;
showing a missing-package action can no longer create an orphan native button
window. Status probes use installation metadata instead of importing unused
Torch/ONNX models into the application. Activating an installed provider is
separate from downloading it. Runtime settings lists omit unavailable providers
without silently changing the saved selection to an online service.

The appearance manager respects an explicitly fixed dialog size instead of
expanding it to hidden pages' minimum hints. The center explicitly clears its
paint surface to avoid stale child-button pixels. Offscreen coverage includes
both themes, all twelve interface languages and 80/100/125/150/200 percent
dialog scales. The final paint correction still needs a native mixed-DPI
recheck: visible testing was paused at the user's request while gaming.

An area-translation provider failure now retains the recognized source in the
editable result workspace. The user can retry or select another provider for
that window without repeating OCR or changing the global provider. Failure
does not write translation history or copy an empty result, including when
successful area results would normally be hidden. The saved automatic-copy
preference still applies to a successful retry. Recovery and provider/workspace
regressions passed 208 tests and 6 subtests with unchanged user data. The real
public Lingva endpoints separately returned HTTP 500 to a neutral test query;
the recovery tests use controlled responses and do not claim to repair that
external service.
