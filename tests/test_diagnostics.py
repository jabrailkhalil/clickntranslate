import json
import zipfile

import diagnostics


def test_bug_report_excludes_histories_document_text_and_runtime_ocr_log(tmp_path, monkeypatch):
    root = tmp_path / "ClicknTranslate"
    data = root / "data"
    logs = data / "logs"
    app = root / "app"
    logs.mkdir(parents=True)
    app.mkdir(parents=True)
    (data / "config.json").write_text(
        json.dumps({
            "interface_language": "ru",
            "ocr_engine": "Windows",
            "secret_api_key": "must-not-leak",
        }),
        encoding="utf-8",
    )
    (data / "copy_history.json").write_text('["private clipboard"]', encoding="utf-8")
    (data / "translation_history.json").write_text('["private translation"]', encoding="utf-8")
    (logs / "ocr_debug.log").write_text("recognized=private document text", encoding="utf-8")
    (app / "ClicknTranslateApp.exe").write_bytes(b"application")
    monkeypatch.setattr(diagnostics, "_portable_root", lambda: root)

    report = diagnostics.create_bug_report(tmp_path / "reports", app_version="test")

    with zipfile.ZipFile(report) as archive:
        names = set(archive.namelist())
        combined = "\n".join(
            archive.read(name).decode("utf-8", errors="replace") for name in names
        )
    assert "report.txt" in names
    assert "HOW_TO_SEND.txt" in names
    assert "environment.json" in names
    assert "safe-config.json" in names
    assert report.parent.name.startswith("ClicknTranslate-bug-report-")
    assert (report.parent / "HOW_TO_SEND.txt").is_file()
    instructions = (report.parent / "HOW_TO_SEND.txt").read_text(encoding="utf-8")
    assert "github.com/jabrailkhalil/clickntranslate/issues" in instructions
    assert "t.me/jabrail_digital" in instructions
    assert "ocr_debug.log" not in combined
    assert "must-not-leak" not in combined
    assert "private clipboard" not in combined
    assert "private translation" not in combined
    assert "private document text" not in combined
    assert "intentionally excluded" in combined
