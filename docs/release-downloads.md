# Release download table

The tag workflow creates a draft from the versioned notes in `docs/RELEASE_<version>.md`. After it uploads Linux and macOS packages, the **Release download table** workflow fills the table from GitHub's uploaded assets. Add signed Windows or Android packages to the same draft when they are ready. To preview their rows, run **Release download table** in Actions and enter the draft's tag. Publishing through GitHub refreshes the table with the final set of files. For automated publication with `GITHUB_TOKEN`, refresh the draft after the last upload, since GitHub can suppress downstream workflow events.

Name each public Android APK for its version and architecture, for example `ClicknTranslate-1.8.3-arm64.apk`. Use `universal` for an APK built for all supported architectures. If the public version name stays the same while Android's build number increases, set the asset label to the actual build number, for example `versionCode=46`. The Android updater can then identify the newer build from the release metadata.

Keep the `clickntranslate-downloads:start` and `clickntranslate-downloads:end` comments around the table when editing notes. The refresh preserves the text outside them. A release description written directly in GitHub receives the table above the existing text.

The Downloads badges use the public GitHub counter for each filename and tag. They become available after publication. VirusTotal links identify the uploaded bytes by GitHub's SHA-256 digest. The optional Actions secret `VIRUSTOTAL_API_KEY` adds a dated result when VirusTotal has analysed the file. The workflow only looks up hashes. “Flagged” counts malicious and suspicious verdicts among engines that completed the analysis.

To preview locally, save the release JSON from GitHub's REST API and render it with `python tools/release_download_table.py --repository OWNER/REPO --preview-json release.json`.
