from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installer_uses_the_verified_launcher_release_layout():
    source = (ROOT / "installer" / "ClicknTranslate.iss").read_text(encoding="utf-8")

    assert '#define MyAppId "{{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}"' in source
    assert 'AppId={#MyAppId}' in source
    assert 'ClicknTranslate-v" + MyAppVersion + "-win64-stage\\ClicknTranslate' in source
    assert "ClicknTranslate-Setup-v{#MyAppVersion}-win64" in source
    assert 'Excludes: "data\\*"' in source
    assert 'Type: filesandordirs; Name: "{app}\\app"' in source
    assert 'Type: filesandordirs; Name: "{app}\\_internal"' in source
    assert "PrivilegesRequired=lowest" in source
    assert "CloseApplications=force" in source
    assert "CloseApplicationsFilter=*.*" in source
    assert "RestartApplications=no" in source


def test_legacy_update_bootstrap_runs_the_verified_inno_installer():
    source = (ROOT / "launcher" / "ClicknTranslateUpdateBootstrap.cs").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_update_bootstrap.ps1").read_text(encoding="utf-8")

    assert '"/CLOSEAPPLICATIONS"' in source
    assert '"/FORCECLOSEAPPLICATIONS"' in source
    assert '"/LOGCLOSEAPPLICATIONS"' in source
    assert "setup.WaitForExit()" in source
    assert "setup.ExitCode != 0" in source
    assert 'Path.Combine(parentDirectory, ".clickntranslate_backup_")' in source
    assert 'FileName = "taskkill.exe"' in source
    assert 'Arguments = "/PID " + process.Id + " /T /F"' in source
    assert "portable-bootstrap.zip" in build
    assert "CompressionLevel NoCompression" in build
