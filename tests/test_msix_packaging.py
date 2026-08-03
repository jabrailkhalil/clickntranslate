import unittest
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TEMPLATE = ROOT / "installer" / "msix" / "AppxManifest.xml.in"
BUILD_SCRIPT = ROOT / "tools" / "build_msix.ps1"
PYINSTALLER_SPEC = ROOT / "ClicknTranslate.spec"
EXE_MANIFEST = ROOT / "installer" / "windows" / "ClicknTranslate.exe.manifest"
ASSET_DIR = ROOT / "installer" / "msix" / "Assets"
SCREENSHOT_DIR = ROOT / "store" / "microsoft-store" / "assets" / "screenshots"


class TestMsixPackaging(unittest.TestCase):
    def test_manifest_has_full_trust_desktop_entry_and_startup_task(self):
        text = MANIFEST_TEMPLATE.read_text(encoding="utf-8")
        rendered = (
            text.replace("__IDENTITY_NAME__", "JabrailDigital.ClicknTranslate.Test")
            .replace("__PUBLISHER__", "CN=Jabrail Digital Test")
            .replace("__PUBLISHER_DISPLAY_NAME__", "Jabrail Digital")
            .replace("__VERSION__", "1.4.7.0")
        )
        root = ElementTree.fromstring(rendered)
        ns = {
            "f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
            "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
            "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
        }

        identity = root.find("f:Identity", ns)
        self.assertEqual(identity.attrib["Version"], "1.4.7.0")
        app = root.find("f:Applications/f:Application", ns)
        self.assertEqual(app.attrib["Executable"], "ClicknTranslate.exe")
        self.assertEqual(app.attrib["EntryPoint"], "Windows.FullTrustApplication")
        startup = root.find(
            "f:Applications/f:Application/f:Extensions/desktop:Extension/desktop:StartupTask",
            ns,
        )
        self.assertEqual(startup.attrib["TaskId"], "ClicknTranslateStartup")
        capability = root.find("f:Capabilities/rescap:Capability", ns)
        self.assertEqual(capability.attrib["Name"], "runFullTrust")

    def test_build_script_excludes_portable_user_data(self):
        text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"data"', text)
        self.assertIn('"CreateShortcut.bat"', text)
        self.assertIn("MakeAppx", text)
        self.assertIn(".msixupload", text)
        self.assertIn('$_.Name -eq "tests"', text)

    def test_main_executable_declares_per_monitor_v2_dpi(self):
        spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")
        manifest = EXE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn("ClicknTranslate.exe.manifest", spec)
        self.assertIn("PerMonitorV2,PerMonitor", manifest)
        self.assertIn('requestedExecutionLevel level="asInvoker"', manifest)

    def test_manifest_assets_have_exact_pixel_sizes(self):
        expected = {
            "StoreLogo.png": (50, 50),
            "Square44x44Logo.png": (44, 44),
            "Square150x150Logo.png": (150, 150),
            "Wide310x150Logo.png": (310, 150),
            "Square310x310Logo.png": (310, 310),
            "SplashScreen.png": (620, 300),
        }
        for name, size in expected.items():
            with self.subTest(name=name):
                with Image.open(ASSET_DIR / name) as image:
                    self.assertEqual(image.size, size)

    def test_store_has_real_desktop_screenshots(self):
        screenshots = sorted(SCREENSHOT_DIR.glob("*.png"))
        self.assertGreaterEqual(len(screenshots), 2)
        for screenshot in screenshots:
            with self.subTest(screenshot=screenshot.name):
                with Image.open(screenshot) as image:
                    self.assertGreaterEqual(image.width, 1366)
                    self.assertGreaterEqual(image.height, 768)


if __name__ == "__main__":
    unittest.main()
