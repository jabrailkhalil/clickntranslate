# Translation requests in 1.7.1

Document and ordinary text translation now share the lossless planner in
`translation_chunks.py`. Documents no longer use an unrelated 1800-character
split before the provider splits the same material again into byte-sized requests.

The planner prefers complete paragraphs, then complete sentences (including CJK
punctuation), then lines/words. A sentence larger than a request budget must still
be split. Unicode code points, boundary whitespace, and original paragraph
separators survive splitting and reassembly. Splitting does not insert blank lines.

## Provider budgets

| Provider | Client request budget | Document batching |
| --- | --- | --- |
| Google public endpoints | 1500 UTF-8 bytes | Individual requests |
| Lingva | 1500 UTF-8 bytes | Individual requests |
| MyMemory | 500 UTF-8 bytes | Individual requests |
| LibreTranslate | 1500 UTF-8 bytes per item | Up to four items per request |
| Hy-MT | 1000 UTF-8 bytes | Individual local generations |
| Argos | 1800 characters per document part | Existing local sentence processing |

The Google/Lingva/LibreTranslate budgets are conservative application settings,
not assertions about their maximum service quotas. MyMemory explicitly specifies
[a 500-byte UTF-8 limit](https://mymemory.translated.net/doc/spec.php).
LibreTranslate documents [an array of texts in `q`](https://docs.libretranslate.com/api/operations/translate/).
Batching reduces HTTP calls; separate array items do not share translation context.

If a LibreTranslate instance rejects batching with HTTP 400/413/422, the remainder
of that operation uses individual requests to the same server. HTTP 429 stops
further online requests for the remaining document; cached results remain usable.
Malformed batch counts or empty results cannot shift translations between items.
The selected engine is now strict in every request path. Batch and individual
failures are reported without switching to Argos or another online provider.
The legacy `allow_online_provider_fallback` configuration key no longer enables
provider substitution. Retrying another endpoint of the same provider, or
retrying a LibreTranslate batch as individual requests to the same server,
still preserves the selected provider.

## Retry and cancellation

Successful document parts and successful subrequests of long ordinary text are
cached separately. Retrying can reuse completed parts while requesting failed or
missing parts. Cache lookups retain language/provider identity; custom
LibreTranslate servers have separate identities. Legacy entries without a provider
are not accepted by this translation path. The existing disposable LRU limit of
1000 cache records still applies; clearing/evicting the cache removes that reuse.

The document's Translate button becomes Stop while translating. Stopping or
closing the window cancels further requests after the current request finishes.
Finished text remains available to save, and a stopped operation is not recorded
as a completed translation. Cancellation is not treated as a provider error and
does not trigger fallback. In-flight HTTP requests/local generations are not
forcibly terminated; the UI states that it is waiting for the current request.

## Verification on 2026-09-06

Windows: 253 tests and 123 subtests passed in the selected translation/UI suite;
the final focused run passed 208 tests and 6 subtests, including the additional
cache validation and cancellation/language checks. Linux: the final combined run
passed 257 tests and 123 subtests, with one platform-specific skip. Missing Argos
dependencies were installed only into the isolated WSL test environment.

Live synthetic English-to-Russian requests succeeded through Google, MyMemory,
Lingva, and LibreTranslate, including a four-item LibreTranslate batch. No saved
user document was used. Local model translation quality was not benchmarked here.

Request-count comparison on synthetic documents, without cache hits:

| Text | Provider | Previous requests | New requests |
| --- | --- | ---: | ---: |
| Russian, 37,410 characters | Google | 60 | 48 |
| Russian, 37,410 characters | LibreTranslate | 60 | 12 |
| Russian, 37,410 characters | MyMemory | 146 | 168 |
| Chinese, 27,902 characters | Google | 62 | 60 |
| Chinese, 27,902 characters | LibreTranslate | 62 | 15 |
| English, 43,170 characters | Google | 50 | 36 |
| English, 43,170 characters | LibreTranslate | 50 | 9 |

These compare request plans, not wall-clock speed or translation quality.
LibreTranslate counts assume the server accepts four-item batches (verified live
on the selected public instance). MyMemory may need more requests to keep whole
sentences under its small byte limit; fewer requests are not guaranteed for every
provider or input.
