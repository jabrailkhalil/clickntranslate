import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_version import APP_VERSION  # noqa: E402


class AppStreamMetadataTest(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "packaging" / "linux" / "io.github.jabrailkhalil.clickntranslate.appdata.xml"
        self.root = ET.parse(self.path).getroot()

    def test_metadata_identifies_a_desktop_application(self):
        self.assertEqual(self.root.tag, "component")
        self.assertEqual(self.root.attrib.get("type"), "desktop-application")
        self.assertEqual(
            self.root.findtext("id"),
            "io.github.jabrailkhalil.clickntranslate",
        )

    def test_metadata_points_at_the_shipped_desktop_entry(self):
        launchable = self.root.find("launchable")
        self.assertIsNotNone(launchable)
        self.assertEqual(launchable.attrib.get("type"), "desktop-id")
        self.assertEqual(
            launchable.text,
            "io.github.jabrailkhalil.clickntranslate.desktop",
        )

    def test_build_script_installs_the_metadata(self):
        script = (ROOT / "tools" / "build_linux_release.sh").read_text(encoding="utf-8")
        self.assertIn("usr/share/metainfo", script)
        self.assertIn(self.path.name, script)
        self.assertIn("appstreamcli validate --no-net", script)
        self.assertIn("--no-appstream", script)

    def test_latest_metadata_release_matches_the_application_version(self):
        release = self.root.find("./releases/release")
        self.assertIsNotNone(release)
        self.assertEqual(release.attrib.get("version"), APP_VERSION)


if __name__ == "__main__":
    unittest.main()
