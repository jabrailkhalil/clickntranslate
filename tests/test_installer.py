from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installer_uses_the_verified_launcher_release_layout():
    source = (ROOT / "installer" / "ClicknTranslate.iss").read_text(encoding="utf-8")

    assert 'AppId={{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}' in source
    assert 'ClicknTranslate-v" + MyAppVersion + "-win64-stage\\ClicknTranslate' in source
    assert "ClicknTranslate-Setup-v{#MyAppVersion}-win64" in source
    assert 'Excludes: "data\\*"' in source
    assert "PrivilegesRequired=lowest" in source
