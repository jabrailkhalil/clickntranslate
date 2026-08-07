"""The build must read its own output back before declaring success.

A build once produced a GUI executable whose embedded PYZ started with a
mebibyte of zeros. Every artifact on disk was intact — the PYZ file and the PKG
archive both verified — so the damage happened while the archive was appended
to the executable, and PyInstaller still exited 0. The app died at startup with
"Failed to setup PYZ archive reader!", and a smoke test that only asked "is the
process alive?" called it healthy, because the error dialog kept it alive.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPECS = ("ClicknTranslate.spec", "ClicknTranslate-linux.spec")


class SpecVerificationTest(unittest.TestCase):
    def _spec(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_both_specs_verify_their_executables(self):
        for name in SPECS:
            source = self._spec(name)
            self.assertIn("_verify_frozen_executables", source, name)
            # It has to actually run, not merely be defined.
            self.assertIn("_verify_frozen_executables(_os.path.join(DISTPATH", source, name)

    def test_verification_runs_after_collect(self):
        for name in SPECS:
            source = self._spec(name)
            collect_at = source.rindex("COLLECT(")
            call_at = source.index("_verify_frozen_executables(_os.path.join(DISTPATH")
            self.assertLess(collect_at, call_at, name)

    def test_every_shipped_executable_is_checked(self):
        expected = {
            "ClicknTranslate.spec": ("ClicknTranslate.exe", "ArgosWorker.exe", "OcrWorker.exe"),
            "ClicknTranslate-linux.spec": ("clickntranslate", "ArgosWorker", "OcrWorker"),
        }
        for name, executables in expected.items():
            source = self._spec(name)
            start = source.index("def _verify_frozen_executables")
            body = source[start:start + 2000]
            for executable in executables:
                self.assertIn(f"'{executable}'", body, f"{name} does not check {executable}")

    def test_failure_stops_the_build(self):
        for name in SPECS:
            source = self._spec(name)
            start = source.index("def _verify_frozen_executables")
            body = source[start:start + 3000]
            self.assertIn("raise SystemExit", body, name)

    def test_corrupt_payload_is_recognised_by_its_magic(self):
        for name in SPECS:
            source = self._spec(name)
            start = source.index("def _verify_frozen_executables")
            body = source[start:start + 3000]
            self.assertIn("startswith(b'PYZ\\0')", body, name)


class VerificationLogicTest(unittest.TestCase):
    """Exercise the check itself, extracted from the spec, against fake payloads."""

    def _load_checker(self):
        source = (ROOT / "ClicknTranslate.spec").read_text(encoding="utf-8")
        start = source.index("def _verify_frozen_executables")
        end = source.index("_verify_frozen_executables(_os.path.join(DISTPATH")
        namespace = {"_os": __import__("os")}
        exec(compile(source[start:end], "spec-fragment", "exec"), namespace)
        return namespace["_verify_frozen_executables"]

    def test_missing_executables_are_reported(self):
        checker = self._load_checker()
        with self.assertRaises(SystemExit) as ctx:
            checker(str(ROOT / "no-such-dist"))

        message = str(ctx.exception)
        self.assertIn("missing from the build", message)
        for executable in ("ClicknTranslate.exe", "ArgosWorker.exe", "OcrWorker.exe"):
            self.assertIn(executable, message)

    def test_the_message_explains_what_to_do(self):
        checker = self._load_checker()
        with self.assertRaises(SystemExit) as ctx:
            checker(str(ROOT / "no-such-dist"))

        message = str(ctx.exception)
        self.assertIn("--clean", message)
        self.assertRegex(message, re.compile("running instance|virus scanner", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
