# Android credential binding

API keys are encrypted in the app's no-backup directory with the existing Android Keystore AES-GCM alias. They never enter settings JSON, profiles, model configuration, exported files or logs.

Each new credential is bound to all of:

- the channel: translation, OCR or speech;
- the provider;
- the private settings context: main settings, an actual saved Room profile, or a fresh settings import;
- the canonical endpoint, or the provider's explicitly shown default API.

The complete identity is authenticated as AES-GCM additional data. Its SHA-256 digest is the filename. Host and scheme case and default ports are normalized; path boundaries and encoded path separators remain significant. User info, query parameters, fragments, remote cleartext endpoints and invalid ports are rejected. Fixed-origin integrations ignore irrelevant leftover custom URL settings.

Changing a server or selecting another profile cannot fall back to a key for a different identity. Two profiles can use different accounts with the same provider and URL. Returning to main settings is an explicit action in Profiles and the screen overlay; it restores the saved main settings and their existing bound keys.

External settings files cannot supply the internal credential context. Exports omit it, imports reject an injected field and allocate a fresh private import context. Profile application re-reads the authoritative Room row and derives the context from its actual ID.

## Earlier encrypted keys

Earlier provider-only v1 files remain read-only and inactive. The key editor reports that a preserved key exists and offers an explicit binding dialog showing the provider, effective server and settings context. Binding decrypts the old envelope and creates a new bound envelope without changing the old file or backup. It refuses to overwrite any existing bound key. Re-entering the key also creates only a bound slot.

## Cancellation

A successful save, removal or explicit binding publishes a process-wide revision after its atomic file write. The translation ViewModel, capture service and speech owners cancel pending work when this changes. Text and photo result publication, capture results, selected overlay actions and cloud speech playback also compare a captured revision directly, so they cannot publish a completion merely because a Flow collector is delayed. Cloud speech checks the gate again after asynchronous media preparation, immediately before starting playback. Studio sessions receive the same direct revision gate.

## Verification sources

- JVM tests: URL identity normalization and rejection, channel/profile/server separation, ciphertext substitution rejection, public/internal JSON separation and MiniMax voice identifier bounds.
- Android integration tests: real Keystore encryption, read-only v1/base/backup binding, no overwrite or fallback, actual Room profile IDs, main profile restoration, injected imports/profile JSON rejection and committed revision events.
- A real loopback HTTP integration test holds a translation response pending, replaces its bound API key and checks ViewModel cancellation and rejection of late result/error publication without an AppShell observer.

Actual executed test counts and device/API coverage belong to the current validation report; the presence of a test source alone does not establish a pass.
