# Repository layout

The root contains at most five files: `README.md`, `LICENSE`, `AGENTS.md`,
`.gitignore` and `.gitattributes`. Application code, developer tools and other
documents live in the directories below.

| Directory | Contents |
| --- | --- |
| `src/` | Python application, `main.py`, `app_version.py`, isolated workers and icons |
| `tools/` | Build, signing and QA tools, native launchers, installers and packaging specs |
| `tools/requirements/` | Python dependencies: `windows.txt`, `linux.txt` and `macos.txt` |
| `tools/shortcuts/` | Windows CMD shortcuts for companion previews and development |
| `tests/` | Automated checks and `pytest.ini` |
| `docs/` | Guides, README translations, demos, privacy policy and citation metadata |
| `components/` | Approved component recipes; generated downloads and runtime data remain ignored |
| `.github/` | GitHub Actions, contribution guide and security policy |

## Run from source

Use Python 3.12 from the repository root:

```sh
python -m pip install -r tools/requirements/windows.txt
python src/main.py
```

Linux and macOS use `tools/requirements/linux.txt` and
`tools/requirements/macos.txt`. Their environment helpers keep the same paths:
`tools/setup_linux_env.sh` and `tools/setup_macos_env.sh`.

Resources live in `src/icons/`. `project_paths.py` resolves both the source
entry and resource directory independently of the current working directory.
For standalone Python probes add `src/` to `PYTHONPATH`.

Moving the entry into `src/` does not move existing source-mode user data:
Windows and writable Linux checkouts still use the repository root. The Mac,
AppImage, MSIX and packaged portable data policies remain unchanged.

## Build and check

- Windows: `tools/build_release.bat` or
  `python -m PyInstaller tools/packaging/ClicknTranslate.spec --clean --noconfirm`.
- Linux: `bash tools/build_linux_release.sh`.
- Mac: `bash tools/build_macos_release.sh` on the native architecture.
- Isolated regression suite: `python tools/run_regression_tests.py`.
- Bounded CI suite: `python tools/run_ci_tests.py`.
- Direct test collection: `python -m pytest -c tests/pytest.ini`.

The build specs resolve inputs from the repository, not from the shell's working
directory. Output remains under `build/`, `dist/` and `releases/`.
User data, credentials, environments and downloaded models are not source files.

## Documentation and Android

The root README remains GitHub's project front page. Additional languages are
under `docs/readme/`; [privacy](PRIVACY.md) and [citation metadata](CITATION.cff)
are under `docs/`.

Android has its own Gradle project in the
[android branch](https://github.com/jabrailkhalil/clickntranslate/tree/android).
See the [Android guide](ANDROID.md). This desktop source reorganization does
not change the Android branch or publish an application release.

## Compatibility

Packaged executable names, signing identities, update protocols and user data
locations stay unchanged. Published release tags and downloads are immutable;
moving source files does not replace their assets or change `APP_VERSION`.
