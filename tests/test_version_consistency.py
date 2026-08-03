import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_release_version_is_synchronized_everywhere():
    version_source = _read("app_version.py")
    match = re.search(r'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', version_source)
    assert match, "APP_VERSION must contain a three-part numeric version"
    version = match.group(1)
    four_part = version + ".0"

    assert version == "1.5.0"
    assert f'#define MyAppVersion "{version}"' in _read("installer/ClicknTranslate.iss")
    assert f'version="{four_part}"' in _read("installer/windows/ClicknTranslate.exe.manifest")
    assert f'version="{four_part}"' in _read("launcher/ClicknTranslateUpdateRepair.manifest")
    assert f'[string]$Version = "{version}"' in _read("tools/stage_release.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_launcher.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_msix.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_update_repair.ps1")
    assert f"/v{version}/ClicknTranslate-v{version}-win64.zip" in _read("tools/build_update_repair.ps1")


def test_readmes_link_to_current_release_assets():
    version = "1.5.0"
    for relative_path in (
        "README.md",
        "docs/readme/README.ru.md",
        "docs/readme/README.zh-CN.md",
        "docs/readme/README.es.md",
        "docs/readme/README.fr.md",
    ):
        content = _read(relative_path)
        assert f"ClicknTranslate-Setup-v{version}-win64.exe" in content
        assert f"ClicknTranslate-v{version}-win64.zip" in content
