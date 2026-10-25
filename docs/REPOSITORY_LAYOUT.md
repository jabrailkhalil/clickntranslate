# Repository layout

Desktop development lives in `main`. The Android application has its own Gradle
project in the [android branch](https://github.com/jabrailkhalil/clickntranslate/tree/android);
see the [Android guide](ANDROID.md) for installation and mobile features.
Both editions publish downloads in the same GitHub Releases page.

The repository has five top-level directories. Downloadable application packages
are attached to GitHub Releases and retain their existing layout.

| Directory | Contents |
| --- | --- |
| `.github/` | Workflows, contribution guide and security policy |
| `src/` | Python implementation, isolated OCR/translation workers and `icons/` |
| `docs/` | Guides, README translations, demos, research paper, historical website sources, store and promotion materials |
| `tests/` | Automated tests |
| `tools/` | Build, signing and QA tools; `packaging/`, `installer/` and native `launcher/` sources |

## Run from source

The entry point and version file stay in the root:

```sh
python main.py
```

Install the dependencies from `requirements.txt`, `requirements-linux.txt`, or
`requirements-macos.txt` for your platform. `main.py` adds `src/` to its import
path. For standalone Python probes, add both the repository root and `src/` to
`PYTHONPATH`. Tests obtain those paths from `pytest.ini`; the regression runner
also passes them to its subprocesses.

Source resources live under `src/icons/`. `project_paths.py` distinguishes source
resources and the root entry point from the resources in a frozen build. Source
user data still follows the existing root entry point; Mac and AppImage user
data keep their existing system locations.

## Build and check

- Windows: `tools/build_release.bat` or
  `python -m PyInstaller tools/packaging/ClicknTranslate.spec --clean --noconfirm`.
- Linux: `bash tools/build_linux_release.sh`.
- Mac: `bash tools/build_macos_release.sh` on the native architecture.
- Isolated regression suite: `python tools/run_regression_tests.py`.
- Bounded CI suite: `python tools/run_ci_tests.py`.

The specs resolve inputs relative to the repository, independently of their
own directory. Build output is still under `build/` and `dist/`; staging and
release tools retain their existing output locations. Local output, downloaded
models, credentials and user data are excluded from Git.

## Website

The current product site is [translate.clickn.dev](https://translate.clickn.dev/).
The author's project hub is [clickn.dev](https://clickn.dev/). The old
`xynapse.online` addresses redirect to those sites. `docs/landing/` preserves
the previous static site source; its historical hosting configuration describes
the former deployment. See its [README](landing/README.md) before using it.

## Compatibility

Keep the packaged executable names, Windows installer AppId, Mac bundle ID,
signing identities, update acknowledgement protocol and user data directories
stable. Windows packages still include `ClicknTranslate.exe`,
`app/ClicknTranslateApp.exe`, private workers, and `program-files.sha256`.

Changing source organization does not replace an existing release asset, create
a new release, or change `APP_VERSION`. Published tags and their files retain
the build inputs and downloads for their respective versions.
