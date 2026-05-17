from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

WINRT_PACKAGES = {
    "winrt-Windows.Foundation.Collections": "winrt.windows.foundation.collections",
    "winrt-Windows.System": "winrt.windows.system",
    "winrt-Windows.Storage": "winrt.windows.storage",
    "winrt-Windows.Graphics.DirectX": "winrt.windows.graphics.directx",
    "winrt-Windows.Graphics.DirectX.Direct3D11": "winrt.windows.graphics.directx.direct3d11",
}


def test_winrt_ocr_runtime_namespaces_are_required():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    normalized_requirements = {line.strip().lower() for line in requirements.splitlines() if line.strip()}

    for package_name in WINRT_PACKAGES:
        assert package_name.lower() in normalized_requirements


def test_winrt_ocr_runtime_namespaces_are_packaged():
    spec_text = (ROOT / "ClicknTranslate.spec").read_text(encoding="utf-8")

    for import_name in WINRT_PACKAGES.values():
        assert import_name in spec_text
