import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_release_version_is_synchronized_everywhere():
    version_source = _read("app_version.py")
    match = re.search(r'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+(?:\.\d+)?)"', version_source)
    assert match, "APP_VERSION must contain a three- or four-part numeric version"
    version = match.group(1)
    four_part = version + ".0" if version.count(".") == 2 else version

    assert version == "1.7.1"
    assert f'#define MyAppVersion "{version}"' in _read("installer/ClicknTranslate.iss")
    assert f'version="{four_part}"' in _read("installer/windows/ClicknTranslate.exe.manifest")
    assert f'version="{four_part}"' in _read("launcher/ClicknTranslateUpdateRepair.manifest")
    assert f'version="{four_part}"' in _read("launcher/ClicknTranslateUpdateBootstrap.manifest")
    assert f'version="{four_part}"' in _read("launcher/ClicknTranslateApplyUpdate.manifest")
    assert f'[string]$Version = "{version}"' in _read("tools/stage_release.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_apply_updater.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_launcher.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_msix.ps1")
    assert f'[string]$Version = "{four_part}"' in _read("tools/build_update_repair.ps1")
    assert f'[string]$Version = "{version}"' in _read("tools/build_update_bootstrap.ps1")
    assert f'[string]$Version = "{version}"' in _read("tools/build_network_setup.ps1")


def test_readmes_link_to_current_release_assets():
    # Download links follow the published release, while APP_VERSION can
    # already describe the next unreleased version under development.
    match = re.search(r'^version:\s*(\d+\.\d+\.\d+)\s*$', _read("CITATION.cff"), re.M)
    assert match
    version = match.group(1)
    for relative_path in (
        "README.md",
        "docs/readme/README.ru.md",
        "docs/readme/README.zh-CN.md",
        "docs/readme/README.es.md",
        "docs/readme/README.fr.md",
    ):
        content = _read(relative_path)
        assert f"Click-n-Translate-{version}-windows-x64-installer.exe" in content
        assert f"Click-n-Translate-{version}-windows-portable-x64.zip" in content
