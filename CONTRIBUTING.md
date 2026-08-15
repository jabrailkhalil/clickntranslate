# Contributing to Click'n'Translate

Click'n'Translate accepts bug reports, reproducible platform reports,
documentation corrections, and focused pull requests. Public discussion takes
place in the GitHub issue tracker so decisions remain visible to users and
reviewers.

## Report a problem

Open an issue at <https://github.com/jabrailkhalil/clickntranslate/issues> and
include:

- the Click'n'Translate version or commit;
- operating system, desktop session, and installation type;
- the selected OCR and translation engines;
- exact steps to reproduce the behavior;
- expected and observed behavior; and
- a minimal screenshot or log excerpt with private text removed.

Do not upload credentials, private documents, complete personal screens, API
tokens, or translation histories. Security-sensitive reports should be sent
privately using the contact method in `SECURITY.md`.

## Prepare a development environment

On Windows, use Python 3.12 and install the runtime plus test dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt pytest
```

On Linux, follow `docs/LINUX.md`; it documents the system packages and the
project's isolated Python environment.

Run the complete automated suite before opening a pull request:

```powershell
python -m pytest -q
```

Platform-specific tests may be skipped when their native API is unavailable.
New behavior should include a focused regression test. Avoid adding network
access to tests unless the behavior cannot be represented with a deterministic
fixture or mock.

## Pull requests

Keep each pull request limited to one problem. Explain the user-visible effect,
the design choice, the test evidence, and any platform not exercised locally.
Do not commit generated builds, downloaded models, personal settings, histories,
credentials, or test screenshots containing private information.

Contributors must follow the Contributor Covenant Code of Conduct at
<https://www.contributor-covenant.org/version/2/1/code_of_conduct/>. By
participating, contributors agree to professional, respectful collaboration.

## Research artifacts

Research papers must identify an immutable commit or release and keep
experiment-specific labels, analysis code, and results outside the application
runtime unless they are generally reusable. Follow `docs/RESEARCH.md` and state
all deviations from a registered or frozen protocol.
