# Android dictionary packs and translation corrections

The library imports public schema 1 SQLite dictionary packs and the existing UTF-8 TSV/JSON formats
through Android's document picker. The SQLite reader and Room storage are independent implementations
using official Android APIs; no previous dictionary engine is reused. File extension alone never
establishes compatibility. Unknown SQLite schemas, MDX, StarDict and archives need separate conversion.
The source document is read only, copied into private staging, and never retained as a persisted URI grant.

## Rich SQLite packs (.bin/.db)

Choose **SQLite (.bin / .db)**. A name is optional: the default comes from the pack. The four required
ordinary tables and their columns are:

| Table | Columns |
| --- | --- |
| `dictionary_metadata` | `key`, `value` |
| `dictionary_entries` | `id`, `headword`, `normalized_headword`, `lemma`, `reading`, `phonetic`, `inflections` |
| `dictionary_forms` | `entry_id`, `normalized_form` |
| `dictionary_senses` | `entry_id`, `position`, `part_of_speech`, `definition`, `form_note` |

`inflections` is a strict JSON string array. Entry ids and sense positions are positive; sense positions
can have gaps. Two articles with the same headword remain separate by their original ids. Metadata must
include `pack_id`, `schema_version=1`, `data_version`, `entry_count`, `source_name`, `source_url`,
`license_name`, `license_url`, and `definition_language`. Unknown metadata keys are retained within bounds.
The pack version is not SQLite `user_version`; valid builder files normally have `user_version=0`.

Known ids establish the source language: `ecdict` → `en`, `jmdict` → `ja`, `korean-basic` → `ko`.
The optional `source_language` extension supplies it for other packs; conflicting known-id language
metadata rejects the file. Without either, the user's selected source language is used. Definitions
always retain the pack's declared language: importing an English–Chinese ECDICT does not make it an
English–Russian dictionary. The library updates its selected pair after import.

SAF is opened once for reading. A streamed private copy is bounded by actual bytes and SHA-256 hashed.
Only finalized standalone UTF-8 SQLite files are accepted; WAL-dependent files and malformed headers
are rejected. The reader opens its own copy with `OPEN_READONLY | NO_LOCALIZED_COLLATORS`. It checks
schema objects and exact column/key contracts **before** `quick_check`, so virtual-table integrity
commands cannot run. Views, triggers, virtual tables and unrelated user tables are rejected. Physical
SQLite corruption remains a corruption error. Text projections use a byte-bound `CASE`, explicitly
cast numeric parameters, and strict UTF-8 decoding before constructing DTOs. SQLite can still allocate
native records while evaluating those projections; this is not a SQLite native heap sandbox guarantee.

Imports use three ordered passes: entries, forms, senses. Each batch has at most 500 records and 1 MiB
payload, with no whole-pack map, per-entry source query, or OFFSET scan. Short Room transactions write
an `IMPORTING` pack. All list, lookup and detail queries show `READY` only. After all passes and actual
counts succeed, one short final transaction publishes it. Cancellation/failure before publication removes
the staged rows in bounded deletes; once the final commit starts, its decision completes. A process-wide
ownership mutex protects imports, exports, deletes and abandoned-row cleanup across Store instances.
Structured pack-flow cleanup removes unfinished packs after process death without blocking visibility
of existing READY packs; it never deletes an active import in another instance. Private reader/export
copies also have scoped cleanup. The app performs no background download or provider request here.

Default SQLite input limits:

| Limit | Maximum |
| --- | --- |
| File | 2 GiB |
| Articles / alias rows / senses | 5 million / 20 million / 20 million |
| Headword or lemma | 16 KiB UTF-8 |
| Normalized key | 64 KiB UTF-8 |
| Reading / phonetic | 16 KiB each |
| Inflections JSON / items | 256 KiB / 1024 strings |
| Definition / form note / POS | 128 KiB / 32 KiB / 4 KiB |
| Metadata | 128 records, 16 KiB per value, 128 KiB total |
| READY packs | 100, shared with flat packs |

Matching recomputes NFKC/trim/lowercase keys and aliases, retaining display strings and all senses.
Exact headword and form queries and BINARY prefix ranges use dedicated normalization indexes. `%`, `_`
and `!` are literal input, never wildcard instructions for rich searches. Search is debounced 250 ms
and cancels prior work. It returns up to 20 rich articles plus the existing flat-format results.
Preview senses show the first three ordered positions, at most 2000 characters per definition/note.
Inflections JSON is read into preview rows only up to 4 KiB; larger values produce an explicit preview
flag instead of loading 256 KiB for every match. Full article views load inflections for one selected
article, show 16 at a time, and page four full senses at a time. Nothing is truncated in stored data.

Rich export produces a standalone schema 1 SQLite `.bin`, preserving ids, readings, phonetics,
inflections, aliases, sense positions, POS, notes, all metadata and attribution. When metadata capacity
permits it adds `source_language`, so an unknown-id pack round-trips without the fallback selector.
If its metadata budget is already full, an unknown-id pack still needs an explicit source on reimport.
Keyset cursor pages are bounded
to 500 records / 1 MiB and closed before independent output batches are written. Dictionary ownership
keeps the source immutable; no Room transaction spans the whole export. History and other Room tables
remain writable. The private output is finalized and checked before the destination document is opened.
Output is also capped at 2 GiB. SAF providers do not offer a universal atomic replace operation: cancelling
the final copy can leave an incomplete newly-created destination, removable with the system picker.

The official [ECDICT release](https://github.com/skywind3000/ECDICT/releases/tag/1.0.28) advertises 3.4 million
words and an upstream SQLite archive. That upstream database is a different schema and is not silently
accepted as this four-table format. No full 207 MB upstream payload has been downloaded or tested for
this implementation. Current coverage uses real synthetic Android SQLite fixtures, including 50,001
reader rows, rich Room import/export/reimport, cancellation, concurrent ownership, corruption, and
EXPLAIN QUERY PLAN checks. Source tests alone are not a claim of a completed device run.

## Dictionary TSV

Choose a pack name and explicit source/target languages in the library screen, then choose TSV.
Each nonblank line has exactly two tab-separated columns: term and definition. The first line may be
`term<TAB>meaning`; UTF-8 BOM and CRLF are accepted. Tabs/newlines inside a definition need JSON instead.
An empty column, extra column, malformed UTF-8, oversized row or invalid control character rejects the
entire import. Example, where the separation is a real tab:

```tsv
term	meaning
hello	привет
world	мир
```

## Dictionary JSON

Select JSON and the same language pair as the document. Object field order is unrestricted. Unknown,
duplicate or incorrectly typed fields are rejected. `name` is optional; the name entered in the UI is
used for the imported pack. Export creates this format:

```json
{
  "format": "clickn-dictionary",
  "version": 1,
  "name": "English → Russian",
  "source": "en",
  "target": "ru",
  "entries": [
    {"term": "hello", "meaning": "привет"},
    {"term": "world", "meaning": "мир"}
  ]
}
```

Every flat-format import creates a separate pack, so existing packs remain intact. Exact duplicate normalized
term+definition pairs within a pack are skipped and counted; distinct definitions for the same term
are retained. NFC/case normalization applies to lookup keys, not displayed text. Search escapes SQL
wildcards supplied by the user, filters by language pair and returns at most 100 results; exact lookup
returns at most 50. Deleting a pack cascades to its own entries only.

Limits: 100 packs, 50000 input rows per pack, 256 characters per term, 8192 per definition, eight MiB
of semantic UTF-8 text per pack and 32 MiB of source bytes. Import streams through bounded UTF-8 decoding
and 250-row Room batches inside one transaction. Cancellation or any failure rolls back the new pack
and its entries, including already flushed batches. Dictionary JSON is parsed by Android's streaming
`JsonReader`; an individual malformed JSON scalar is additionally bounded by the source byte limit.

## Corrections

The library lets users create, edit, delete, search, import and export corrections. Corrections apply
before contacting a translation provider. New rules default to an explicit language pair and a
case-sensitive NFC/whitespace-normalized original text key. Rules may explicitly select wildcard
languages, an application, case-insensitive matching and small OCR differences. Unknown source language
does not activate another explicit source language. Both corrected and observed text aliases can match.
Import preserves
existing corrections for duplicate keys; an explicit edit can replace a correction.

```json
{
  "format": "clickn-corrections",
  "version": 1,
  "entries": [
    {"original": "Hello world", "translated": "Здравствуйте, мир", "source": "en", "target": "ru"}
  ]
}
```

The reader retains version 1 compatibility. Current exports use version 2, adding all six metadata
fields to every entry: `observedSource`, `scopePackage`, `scopeLabel` (strings), and `caseSensitive`,
`fuzzy`, `enabled` (booleans). A version 2 entry must carry all fields; malformed/unknown fields reject
the transaction. Empty language/application strings denote deliberately global rules. Explicit app
rules require separate Android usage access during screen capture, never inferred from a label.
Normal text/photo input has no external-app context and uses global rules only.

Exact corrections precede fuzzy matching. OCR tolerance is limited to 12..1000 Unicode code points,
at most three edits, and at most 100 eligible database candidates. Ambiguous/overfull candidate sets
return no replacement. This is an independent conservative policy, not the former fuzzy algorithm.

Corrections use JSON only, with strict fields/types and streaming parsing. Limits: 10000 corrections,
100000 characters per original/translation, two million stored characters in total and 32 MiB source
bytes. A failed import rolls back all newly imported corrections. Exports use bounded database pages
inside a read transaction and write directly to the selected document; cancelled or failed exports
can leave an incomplete destination document, which can be deleted through the system file picker.

## Storage upgrade

Room version 2 adds `dictionary_packs`, `dictionary_entries` and `corrections` to the existing
`clickn_next_v1.db` file. `LIBRARY_MIGRATION_1_2` only creates these tables/indexes and never alters old
history, glossary, profile or import-marker rows. The frozen v1 schema is retained under `app/schemas`.
`LibraryMigrationTest` creates an actual v1 SQLite file with all four old tables and identity metadata,
opens it through Room v5 with the registered migration chain, and verifies the retained rows and writable
new tables. Tests must be run on Android; having this test in source does not imply it has passed.

`RULES_MIGRATION_3_4` adds glossary/correction metadata and replaces only their unique indices; IDs,
history, dictionary packs, profiles, receipts and original text remain intact. Version 3 corrections
remain case-sensitive, enabled and exact. The frozen v3 schema and a real-file upgrade test verify this
contract when run. Rule writes publish a process-wide revision after commit to cancel stale translations.

`DICTIONARY_MIGRATION_4_5` adds state and source/license metadata to dictionary packs and creates
`dictionary_lexemes`, `dictionary_aliases`, `dictionary_rich_senses` and `dictionary_pack_metadata`.
Existing packs default to READY/FLAT. Existing flat entries, history, corrections, glossary, profiles
and import receipts remain unchanged. Composite primary-key prefixes cover cleanup and foreign-key
lookups; only the headword/form normalization secondary indexes are added for rich entries. Real-file
v4→v5 tests assert exact target version, retained data, new defaults and foreign-key consistency.

Legacy production databases remain separate and untouched. Their supported public text can still be
transferred through `LegacyImporter`; public schema 1 dictionaries use the new explicit SQLite import.
Unknown binary formats remain unsupported. Credential transfer is handled separately.
