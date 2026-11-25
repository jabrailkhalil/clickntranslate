# New Android storage

This implementation uses `clickn_next_v1.db` (Room), `clickn_next_settings_v1.preferences_pb`
(Preferences DataStore), and `noBackupFilesDir/clickn_next_credentials_v1` (encrypted API keys).
Legacy files are read only by the explicit importer; none is opened for writing, migrated destructively,
renamed, or deleted.
Previously installed user data remains on disk. `LegacyImporter.preview()` reads supported old data;
`importPreview(preview)` explicitly transfers supported text/history/glossary and creates a
credential-free **Legacy settings** profile. Current new preferences are preserved. Optional
`applySettings=true` can initialize preferences only when the new settings file has never been written.
Import markers and new rows commit in one Room transaction, so re-import does not duplicate history.
Keeping the application ID does not itself establish signing compatibility.

Room owns translations, glossary terms and profiles. The history UI uses Room Paging 3 (30 rows per
page, at most 90 loaded rows, no placeholders) and SQL searches the entire history. A compatibility
flow still observes the latest 2000 rows; the UI does not use it. Room v3 adds a separate
`translation_search` table with Kotlin `Locale.ROOT` lowercase text. Source and translated originals
remain unchanged. Insert and search indexing commit together; deleting history cascades to its index.
Both migration paths v1→v2→v3 and v2→v3 retain existing tables. Backfill reads IDs in pages and UTF-8
text in small blob chunks, including multibyte characters and embedded NULs; it does not put an
oversized old translation into one CursorWindow. Paging still returns an original translation row:
an unusually large preexisting single row can exceed a device's SQLite CursorWindow limit. No row
is silently truncated or deleted to bypass that platform limit.

Full history export uses SAF and writes UTF-8 in 20-row keyset pages off the main thread, with
cancellation checks and 4096-character writer chunks. A frozen upper ID excludes later insertions,
including backdated ones; concurrent external deletions can remove rows before their page is read.
No full-history string/list or long write-blocking transaction is created. Profiles store the same
versioned public settings document as export.
Import validates the full document before one atomic DataStore edit. Unknown fields, including
credential fields, are rejected, as are malformed language identifiers, enums, numeric bounds,
rectangles and URLs. Endpoints cannot contain URL credentials or query/fragment tokens. Settings
and profiles contain no API-key field. Clearing history deletes translations in the new database only.

API-key bytes are encrypted using AES-256-GCM with fresh platform-generated IVs and a non-exportable
Android Keystore key. Associated authenticated data binds the format version and provider identity.
AtomicFile writes ciphertext inside Android's no-backup directory. There is no plaintext persistence,
backup fallback or key logging. An absent credential returns an empty string; corrupt ciphertext or
an unavailable Keystore key produces an error instead of silently resetting credentials. Users may
enter the key again. The platform can prevent key extraction; this does not protect a credential while
the process is actively using it on a compromised device.

JVM tests cover settings round trips, strict import validation, GCM tamper detection, provider binding,
wrong keys, malformed envelopes and nonce uniqueness. Android instrumentation must additionally
verify Room/DataStore I/O, Keystore-backed key lifecycle, atomic file recovery, process recreation,
on-device backup exclusion and upgrades from a signed legacy build. JVM crypto tests do not establish
hardware-backed key availability.

## Legacy transfer coverage

The legacy schema was inspected from the repository's `android` branch. The importer is new code;
it does not load old repositories, serializers, libraries, native binaries or algorithm implementations.

- `files/datastore/clickntranslate_settings.preferences_pb`: supported public language, engine,
  font/button size, timing and capture-region keys only. Pixel regions require the saved screen
  dimensions to convert to normalized coordinates. Invalid fields are individually reported.
- `shared_prefs/locale_prefs.xml`, `theme_prefs.xml`, `clickn_floating_picture.xml`: interface language,
  corresponding new theme and one of the six project mascots. Old paper themes map to light/dark.
- `shared_prefs/clickn_text_history.xml`: the `entries` JSON list is imported as text history, keeping
  original text, translation, language pair, provider name and timestamp.
- `gallery-translation.db`: completed gallery items become image history with textual results.
  Images, bounding boxes, tasks, queue status and original metadata remain in their original storage.
- `translation-memory.db`: corrected source/translation pairs become readable history and independently
  imported correction rules with observed/corrected aliases, language/application scope, case and
  fuzzy flags. If legacy memory was globally disabled, imported rules stay disabled. Bounds and
  conflicts are reported; current rules win and source data stays intact.
- `translation-glossary.db`: terms retain source/target languages, application scope, category,
  case sensitivity and enabled state. An unknown source cannot activate an explicitly different
  source language; ordinary text/photos have no external-app scope. Optional UsageStats evidence
  is required for scoped screen rules, with failure closed when access or unambiguous evidence is
  absent. Existing terms win same-rule conflicts. The editor exposes advanced restrictions explicitly.
- Public endpoints, prompts and `translation_presets_json` can be read in the legacy
  `enc:v1:ak:` metadata format using **only an existing** Android Keystore alias
  `clickntranslate_settings_secret_aes_gcm_v1`. No old key is created or replaced. Missing alias,
  failed GCM authentication, invalid UTF-8, oversized data and `fb:`/unknown envelopes are reported;
  the original remains intact. Plain public metadata from earlier schemas is also supported.
  This public-metadata reader excludes API keys and `local_preset_credentials_v1_*`. A separate,
  explicitly confirmed credential transfer reads only the selected supported per-preset record,
  validates its authenticated owner/group/binding and exact new profile/server identity, and writes
  a new fully bound envelope without replacing a target ciphertext or `.bak`. Missing old aliases
  are never created. Global credentials and unsupported formats/services require manual entry.
  See [credential transfer boundaries](ANDROID_LEGACY_CREDENTIAL_PLAN.md). Neither path changes
  the source store or calls a provider. Unsupported engines and model files remain in legacy storage.
- Public presets become separate, **inactive** `Legacy · <name>` profiles. Names already present in
  the new app are preserved; new imports receive a numeric suffix. Profile rows and stable hashed
  legacy-ID receipts commit in one Room transaction. Retry does not create another profile or switch
  current preferences. LLM endpoint/model defaults omitted by the old serializer are not inferred:
  imported fields stay empty, and preview warns that the profile needs review. Explicit legacy
  OPENAI endpoints identify official OpenAI/DeepSeek only at their known HTTPS hosts and API paths;
  other configured servers remain OpenAI-compatible. ANTHROPIC/DEEPL/DEEPSEEK and explicit compatible
  enums retain their supported provider. Source/target, supported OCR, text size, prompt and bounded
  output-token options transfer when explicitly stored. Missing target language is reported for review.
  DeepL custom protocols without a matching adapter require manual endpoint selection.

Public metadata is limited to 2 MiB decoded UTF-8, nesting depth 16 and 100 preset entries. Fields
are type-checked and passed through the new settings validation; bad entries are reported individually.
Only supported public fields enter profile JSON. Tests use synthetic encrypted metadata, an injected
existing-key reader and temporary DataStore/in-memory Room fixtures to check mapping, no-key/tamper
failures, duplicate retries, current-setting preservation and unchanged legacy-file hashes. A real
production-signed upgrade is still required to establish access to the installed legacy Keystore key.

Preview bounds each database to 10000 rows, individual text to 200000 characters and aggregate SQL
text to eight million characters. Excess data remains in legacy storage and appears in warnings.
The old application allowed Android backup but explicitly included only shared preferences and excluded
text history. The new app disables backup; secret ciphertext is separately stored in `noBackupFilesDir`.
Real signed upgrade, full schema variants and unsupported metadata remain unverified on hardware.

## Persistent photo jobs (Room6)

The additive v5→v6 migration creates photo job/item tables and keeps all existing history, profile,
dictionary and rule tables. A job keeps private copies only of images explicitly selected for that
job. The application never saves screen-capture frames into this store. Limits are 20 items per job,
64MiB per source, 128MiB per job, 256MiB across the store and 30 jobs. Preview and OCR decoding remain
bounded independently of compressed file size. Results use bounded separate files, not Room blobs.

Opening the store repairs interrupted RUNNING records to resumable states and removes only validated
owned orphan files. It does not translate, download models or repeat network requests. Resume/Retry
are explicit. If relevant settings differ, the UI lists the differences and can make a new job with
current settings; the original job, sources and history remain. Stored job settings do not activate
an old credential scope. Settings, secret and rule changes revoke in-flight work before publication.

Each accepted item result and its history receipt commit in one transaction behind the active run
token. Recovery retains an existing receipt, and stale completion cannot create a second history row.
Deleting a job requires confirmation and removes only that job's validated owned files/rows, while
the user's original documents and independent history remain. PNG and whole-folder export use the
explicitly granted SAF destinations. AtomicFile recovery is applied before orphan cleanup.

Independent platform references: [DataStore](https://developer.android.com/topic/libraries/architecture/datastore),
[Room](https://developer.android.com/training/data-storage/room),
[Android Keystore](https://developer.android.com/privacy-and-security/keystore).
