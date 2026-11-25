# Japanese SFX starter v1 — provenance and scope

Files: `app/src/main/assets/dictionaries/sfx_ja_en_v1.tsv` and `sfx_ja_ru_v1.tsv`.
Both are new UTF-8 text assets written for this Android rewrite on 2026-10-24. They contain eight common
Japanese onomatopoeic expressions in katakana and hiragana spellings (16 rows per language pair).
The English and Russian explanations were composed specifically for this project. No old application
dictionary, proprietary/binary pack, external dictionary dump, screenshots, artwork or example sentences
were copied. Ordinary Japanese words are vocabulary facts, not a reused dictionary implementation.
The new source assets follow the repository's source licensing; no external dictionary data license
is claimed or required for an imported dataset because no such dataset is included.

The Japan Foundation's independent
[onomatopoeia content index](https://www.hikidasu.jpf.go.jp/en/corner/onomatopoeia/) was consulted as
general linguistic context confirming common vocabulary (including どきどき, ばたばた, わくわく and
きらきら). Its video scripts, definitions, translations and media are not included. These starter
descriptions are short contextual hints, not an authoritative or exhaustive Japanese dictionary.
Sounds and feelings are context-dependent; a drawing may require a different translation.

Import is an explicit button in Library. Nothing is installed automatically and the entries are never
added to the global translation glossary. Russian UI imports **ja→ru**; all other UI languages import
**ja→en**, with the real pair shown on the button and resulting pack. Repeating import returns the
existing starter pack instead of making another copy. Deleting it allows a fresh explicit import.
Pack+identity marker commit in one Room transaction, without a database schema change.

`LibraryIntegrationTest.starterSampleIsExplicitSmallLanguageBoundAndDoesNotInstallTwice` verifies the
absence of startup installation, several ordinary terms, language binding, duplicate prevention,
reinstallation after deletion, English fallback and absence of global glossary writes. JVM format tests
check the fallback mapping and fixed asset paths. Actual execution status belongs in the test report.
