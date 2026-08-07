"""Installing a Windows OCR language has to be legible while it runs.

The work is done by Windows Update through dism.exe, which routinely holds one
percentage for many minutes. Elapsed time alone cannot tell the user whether
that is a slow download or a wedged one, so the elevated script also reports
Windows Update's own download progress and how long nothing at all has moved —
CBS.log growing is the signal sysadmins use for exactly this question.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from settings_window import (  # noqa: E402
    OcrLanguageManagerDialog,
    language_manager_text,
)

LANGUAGES = ("en", "ru", "es", "de", "fr", "zh")


class _Parent(QWidget):
    def __init__(self):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = "Темная"


class _Owner(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.tesseract_path = ""
        self.easyocr_status = (False, "missing")
        self.rapidocr_status = (False, "missing")
        self.last_progress_owner = None
        self._tesseract_install_in_progress = False
        self._easyocr_install_in_progress = False
        self._rapidocr_install_in_progress = False
        self._hymt_install_in_progress = False
        self.package_task_status = None

    def _find_available_tesseract_exe(self):
        return self.tesseract_path

    def _easyocr_importable_status(self):
        return self.easyocr_status

    def _rapidocr_importable_status(self):
        return self.rapidocr_status

    def _local_easyocr_dir(self):
        return str(ROOT / "ocr" / "easyocr")

    def _hymt_installed(self):
        return False

    def _local_hymt_dir(self):
        return str(ROOT / "translators" / "hymt")

    def set_language_package_task_status(self, text="", percent=None, kind="running"):
        self.package_task_status = (text, percent, kind)


class WindowsOcrProgressTextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _Parent()
        self.owner = _Owner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.dialog = OcrLanguageManagerDialog(self.owner)
        self.emitted = []
        emit_patch = mock.patch.object(
            OcrLanguageManagerDialog,
            "_emit_language_progress",
            lambda _self, text, percent, determinate: self.emitted.append(
                (text, percent, determinate)
            ),
        )
        self.addCleanup(emit_patch.stop)
        emit_patch.start()

    def tearDown(self):
        self.dialog.close()
        self.owner.close()
        self.parent.close()

    @staticmethod
    def _status(**overrides):
        status = {
            "phase": "installing",
            "percent": 34,
            "current": 1,
            "total": 2,
            "code": "ru",
            "elapsed": 192,
            "download": -1,
            "quiet": 0,
        }
        status.update(overrides)
        return status

    def test_the_bar_is_real_and_the_clock_is_shown(self):
        self.dialog._emit_windows_ocr_status(self._status())
        text, percent, determinate = self.emitted[-1]

        self.assertEqual(percent, 34)
        self.assertTrue(determinate, "dism reports a real percentage; do not marquee it")
        self.assertIn("03:12", text)
        self.assertIn(
            language_manager_text("en", "win_stage", stage=3, current=1, total=2),
            text,
        )
        self.assertIn(language_manager_text("en", "win_time_unknown"), text)
        # The bar below the message already shows the percentage.
        self.assertNotIn("34%", text)

    def test_windows_update_download_is_named_separately_from_the_component(self):
        """The two real percentages must never look like whole-job progress."""
        self.dialog._emit_windows_ocr_status(self._status(download=49))
        text = self.emitted[-1][0]

        self.assertIn(language_manager_text("en", "win_download_stage", percent=49), text)
        self.assertIn(language_manager_text("en", "win_activity_recent"), text)

    def test_no_download_line_when_windows_reports_none(self):
        self.dialog._emit_windows_ocr_status(self._status(download=-1))
        text = self.emitted[-1][0]

        self.assertNotIn(language_manager_text("en", "win_download_stage", percent=0), text)

    def test_a_long_silence_is_explained_rather_than_left_to_guesswork(self):
        quiet = self.dialog.WINDOWS_OCR_QUIET_WARNING_SECONDS + 60
        self.dialog._emit_windows_ocr_status(self._status(quiet=quiet))
        text = self.emitted[-1][0]

        self.assertIn(language_manager_text("en", "win_quiet", minutes=quiet // 60), text)
        # It says what to do about it, which is the point of showing it at all.
        self.assertIn("cancel", text.lower())

    def test_a_normal_pause_is_not_called_out(self):
        """Windows sits on one percentage for minutes as a matter of course;
        warning about that would train the user to ignore the warning."""
        self.dialog._emit_windows_ocr_status(self._status(quiet=120))
        text = self.emitted[-1][0]

        self.assertNotIn(language_manager_text("en", "win_quiet", minutes=2), text)

    def test_every_language_has_the_new_lines(self):
        for lang in LANGUAGES:
            stage = language_manager_text(lang, "win_download_stage", percent=49)
            quiet = language_manager_text(lang, "win_quiet", minutes=6)
            info = language_manager_text(lang, "win_background_info")
            lifecycle = language_manager_text(
                lang, "win_stage", stage=3, current=1, total=2
            )
            unknown = language_manager_text(lang, "win_time_unknown")
            show = language_manager_text(lang, "show_progress")
            installing = language_manager_text(lang, "task_installing_short")
            packages = language_manager_text(lang, "task_packages_short")
            busy = language_manager_text(lang, "task_busy_help")
            component = language_manager_text(lang, "win_component_short", percent=58)
            self.assertIn("49", stage, lang)
            self.assertIn("6", quiet, lang)
            self.assertIn("3", lifecycle, lang)
            self.assertIn("1", lifecycle, lang)
            self.assertIn("2", lifecycle, lang)
            # The expectation has to carry a number, or it says nothing useful.
            self.assertRegex(info, r"\d", lang)
            self.assertIn("58", component, lang)
            for value in (stage, quiet, info, lifecycle, unknown, show, installing, packages, busy, component):
                self.assertTrue(value, (lang, value))
                self.assertNotIn("{", value, lang)


class WindowsOcrInstallerScriptTest(unittest.TestCase):
    """The elevated script is what produces those numbers."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _Parent()
        self.owner = _Owner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.dialog = OcrLanguageManagerDialog(self.owner)
        self.script = self.dialog._windows_ocr_installer_script(
            ["ru"],
            ["Language.OCR~~~ru-RU~0.0.1.0"],
            [],
            r"C:\tmp\status.json",
            r"C:\tmp\cancel.request",
            r"C:\tmp\result.txt",
            r"C:\tmp",
        )

    def tearDown(self):
        self.dialog.close()
        self.owner.close()
        self.parent.close()

    def test_it_reads_windows_update_progress_from_the_cbs_log(self):
        self.assertIn("CBS.log", self.script)
        # "DownloadProgress: [ 49 / 100 ]" is what CBS writes while the payload
        # comes down; it is the only live signal during a long pause.
        self.assertIn("DownloadProgress", self.script)
        self.assertIn("FileShare]::ReadWrite", self.script)

    def test_it_reads_only_the_tail_of_that_log(self):
        """CBS.log runs to tens of megabytes; reading it whole every 250 ms
        would cost more than the install."""
        self.assertIn("65536", self.script)
        self.assertIn("SeekOrigin]::End", self.script)

    def test_it_reports_how_long_nothing_has_moved(self):
        self.assertIn("quiet = $Script:QuietSeconds", self.script)
        self.assertIn("$lastMovement", self.script)
        self.assertNotIn(
            "$moved = ($cbs.Length -gt $cbsLength)",
            self.script,
            "CBS repeats one unchanged line forever; file growth is not progress",
        )

    def test_the_bar_is_for_the_current_component_not_a_fake_whole_job(self):
        self.assertIn("Write-OcrStatus $Phase $rawPercent", self.script)
        self.assertNotIn("$stepPercent", self.script)
        self.assertNotIn("$overall", self.script)

    def test_it_reports_a_pending_restart_instead_of_claiming_success(self):
        self.assertIn("3010", self.script)
        self.assertIn("OK_RESTART", self.script)

    def test_the_status_payload_stays_valid_json(self):
        payload = self.script.split("$payload = @{")[1].split("} | ConvertTo-Json")[0]
        for field in ("phase", "percent", "elapsed", "download", "quiet", "restart"):
            self.assertRegex(payload, rf"\b{field}\s*=", field)

    def test_it_does_not_read_that_log_on_every_tick(self):
        """The loop spins four times a second to keep Cancel responsive; CBS.log
        runs to tens of megabytes."""
        self.assertIn("($tick % 8) -eq 1", self.script)

    def test_the_script_has_no_unresolved_placeholders(self):
        leftovers = re.findall(r"\{[a-z_]+\}", self.script)
        self.assertEqual(leftovers, [], leftovers)


class ProgressDialogFitsItsMessageTest(unittest.TestCase):
    """Windows OCR reserves its final message size before work begins."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_windows_dialog_does_not_jump_when_the_long_status_arrives(self):
        from settings_window import TesseractInstallProgressDialog

        host = QWidget()
        dialog = TesseractInstallProgressDialog(host, title="Windows OCR")
        dialog.show()
        self.app.processEvents()
        dialog.setLabelText("Windows OCR: installing Russian (1/2)…\n03:12")
        self.app.processEvents()
        short = dialog.size()

        dialog.setLabelText(
            "Windows OCR: installing Russian (1/2)…\n"
            "12:21 · Windows Update: 49% downloaded\n"
            + language_manager_text("en", "win_quiet", minutes=6)
        )
        self.app.processEvents()
        tall = dialog.size()

        self.assertEqual(tall, short, "the progress window visibly changed size")
        label = dialog.message_label
        self.assertGreaterEqual(
            label.height(),
            label.heightForWidth(max(1, label.width())),
            "the label is shorter than its own text needs",
        )
        dialog.close()
        host.close()
        self.app.processEvents()


class BackgroundProgressCanBeReopenedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_background_status_is_persistent_and_reopens_the_same_task(self):
        from settings_window import TesseractInstallProgressDialog

        parent = _Parent()
        owner = _Owner(parent)
        manager = OcrLanguageManagerDialog(owner)
        progress = TesseractInstallProgressDialog(manager, title="Windows OCR")
        manager.progress_dialog = progress
        manager._install_in_progress = True
        manager.show()
        progress.show()
        self.app.processEvents()

        progress._continue_in_background()
        manager._on_task_backgrounded("Windows OCR", "Installing Russian")
        self.app.processEvents()

        self.assertFalse(progress.isVisible())
        self.assertTrue(manager.task_show_button.isVisible())
        self.assertEqual(owner.package_task_status[2], "running")

        manager._restore_task_progress()
        self.app.processEvents()

        self.assertTrue(progress.isVisible())
        self.assertFalse(progress._user_minimized)
        self.assertFalse(manager.task_show_button.isVisible())

        manager._install_in_progress = False
        progress.close()
        manager.close()
        owner.close()
        parent.close()

    def test_compact_windows_status_names_the_component_percentage(self):
        parent = _Parent()
        owner = _Owner(parent)
        manager = OcrLanguageManagerDialog(owner)
        manager._active_language_task_title = "Windows OCR"

        manager._show_task_status(
            "Step 2/4 · Language 3/3\nWindows is preparing Italian", 58
        )

        self.assertIn("DISM 58%", manager.task_status_label.text())
        self.assertNotIn("preparing Italian", manager.task_status_label.text())
        self.assertIn("preparing Italian", manager.task_status_label.toolTip())
        manager.close()
        owner.close()
        parent.close()


class PackageTaskConcurrencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _Parent()
        self.owner = _Owner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.manager = OcrLanguageManagerDialog(self.owner)

    def tearDown(self):
        self.manager.close()
        self.owner.close()
        self.parent.close()

    def test_mutating_actions_are_disabled_but_table_selection_is_preserved(self):
        actions = [
            button
            for button in self.manager.findChildren(QWidget)
            if getattr(button, "objectName", lambda: "")() == "languagePackageAction"
        ]
        self.assertTrue(actions)
        table = self.manager.tesseract_table
        table._pending_package_codes = {"de"}

        self.manager._set_package_actions_busy(True)

        self.assertTrue(all(not button.isEnabled() for button in actions))
        self.assertFalse(self.manager.refresh_btn.isEnabled())
        self.assertEqual(table._pending_package_codes, {"de"})
        self.assertIn("preserved", actions[0].toolTip())

        self.manager._set_package_actions_busy(False)
        self.assertTrue(all(button.isEnabled() for button in actions))
        self.assertTrue(self.manager.refresh_btn.isEnabled())
        self.assertEqual(table._pending_package_codes, {"de"})

    def test_a_second_task_reopens_the_first_instead_of_starting(self):
        current = mock.Mock()
        self.manager.progress_dialog = current
        self.manager._install_in_progress = True
        worker = mock.Mock()

        self.manager._run_language_task("Tesseract", ["de"], worker)

        current.restore_from_background.assert_called_once_with()
        worker.assert_not_called()


class WindowsOcrFailureAdviceTest(unittest.TestCase):
    """A failure has to say the true thing about this machine.

    "Restart Windows and try again" was shown for anything whose text merely
    contained the word "restart" — including a servicing stack that was simply
    busy, on a machine with no pending reboot at all. That sends the user away
    for five minutes to fix nothing.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _Parent()
        self.owner = _Owner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.dialog = OcrLanguageManagerDialog(self.owner)

    def tearDown(self):
        self.dialog.close()
        self.owner.close()
        self.parent.close()

    def _advice(self, raw, reboot_pending):
        with mock.patch.object(
            OcrLanguageManagerDialog, "_windows_reboot_pending", return_value=reboot_pending
        ):
            return self.dialog._friendly_windows_ocr_error(raw)

    def test_a_broken_script_is_not_blamed_on_windows(self):
        """The failure that started this: PowerShell rejected the generated
        script, the parser error quoted the line holding OK_RESTART, and a bare
        "restart" match turned a bug of ours into "Windows is busy"."""
        raw = "\n".join((
            "install.ps1:253 char:46",
            "+ $resultText = if ($Script:RestartRequired) OK_RESTART else OK",
            "+ CategoryInfo : ParserError: (:) [], ParentContainsErrorRecordException",
            "+ FullyQualifiedErrorId : MissingStatementBlock",
        ))
        advice = self._advice(raw, False)

        self.assertEqual(advice, language_manager_text("en", "win_error_generic"))
        self.assertNotEqual(advice, language_manager_text("en", "win_error_busy"))
        # And the text that names the real cause is kept for the Details pane.
        self.assertIn("MissingStatementBlock", self.dialog._last_task_error_details)

    def test_busy_servicing_without_a_pending_reboot_does_not_ask_for_one(self):
        advice = self._advice("The servicing operation cannot start; please restart", False)

        self.assertEqual(advice, language_manager_text("en", "win_error_busy"))
        self.assertIn("no restart", advice.lower())

    def test_a_real_pending_reboot_asks_for_the_restart(self):
        advice = self._advice("0x800f0922", True)

        self.assertEqual(advice, language_manager_text("en", "win_error_restart"))

    def test_a_second_dism_session_is_reported_as_busy(self):
        """0x800f0902 is 'another servicing operation is running'."""
        self.assertEqual(
            self._advice("Add-WindowsCapability failed. Error code = 0x800f0902", False),
            language_manager_text("en", "win_error_busy"),
        )

    def test_policy_and_source_failures_keep_their_own_advice(self):
        self.assertEqual(
            self._advice("Error code = 0x800f0954", False),
            language_manager_text("en", "win_error_policy"),
        )
        self.assertEqual(
            self._advice("HRESULT = 0x800f0906 - CBS_E_DOWNLOAD_FAILURE", False),
            language_manager_text("en", "win_error_source"),
        )

    def test_the_raw_text_is_kept_for_the_details_pane(self):
        raw = "DISM exited with code 1726 for Language.OCR~~~fr-FR~0.0.1.0"
        self._advice(raw, False)

        self.assertEqual(self.dialog._last_task_error_details, raw)

    def test_every_language_has_both_messages(self):
        for lang in LANGUAGES:
            for key in ("win_error_restart", "win_error_busy"):
                value = language_manager_text(lang, key)
                self.assertTrue(value and value != key, (lang, key))
            self.assertNotEqual(
                language_manager_text(lang, "win_error_restart"),
                language_manager_text(lang, "win_error_busy"),
                lang,
            )


class WindowsServicingIsSerialisedTest(unittest.TestCase):
    """dism.log showed three sessions against the online image inside the same
    second — the tab, the runtime probe and the verification all asking at once.
    Overlapping sessions are what makes Windows answer "servicing is busy"."""

    def test_the_capability_query_takes_the_servicing_lock(self):
        import inspect

        import settings_window

        source = inspect.getsource(
            settings_window.OcrLanguageManagerDialog._windows_ocr_capability_catalog
        )
        self.assertIn("_WINDOWS_SERVICING_LOCK", source)
        # And the lock is process-wide, not per dialog.
        self.assertFalse(
            hasattr(settings_window.OcrLanguageManagerDialog, "_WINDOWS_SERVICING_LOCK")
        )
        self.assertTrue(hasattr(settings_window, "_WINDOWS_SERVICING_LOCK"))

    def test_the_elevated_install_holds_the_same_lock_until_it_exits(self):
        import inspect
        import settings_window

        source = inspect.getsource(
            settings_window.OcrLanguageManagerDialog._install_windows_ocr_worker
        )
        run_installer = source[source.index("def run_installer"):source.index(
            "threading.Thread(target=run_installer"
        )]
        self.assertIn("with _WINDOWS_SERVICING_LOCK", run_installer)


class GeneratedPowerShellParsesTest(unittest.TestCase):
    """Run PowerShell's own parser over every script this app generates.

    These scripts are built with f-strings, so a literal brace has to be
    doubled. A single one is not a Python error — ``{ 'OK_RESTART' }`` is a
    valid f-string expression — so it silently produced
    ``if ($Script:RestartRequired) OK_RESTART else OK``, which PowerShell
    rejects with MissingStatementBlock. The install died before dism.exe was
    ever started, and the app reported it as a busy servicing stack.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _Parent()
        self.owner = _Owner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.dialog = OcrLanguageManagerDialog(self.owner)

    def tearDown(self):
        self.dialog.close()
        self.owner.close()
        self.parent.close()

    def _scripts(self):
        codes = ["ru", "fr"]
        capabilities = [
            "Language.OCR~~~ru-RU~0.0.1.0",
            "Language.OCR~~~fr-FR~0.0.1.0",
        ]
        paths = (
            os.path.join("C:\\", "tmp", "status.json"),
            os.path.join("C:\\", "tmp", "cancel.request"),
            os.path.join("C:\\", "tmp", "result.txt"),
            os.path.join("C:\\", "tmp"),
        )
        return {
            # The installer also takes the codes it should reinstall to repair.
            "installer": self.dialog._windows_ocr_installer_script(
                codes, capabilities, ["ru"], *paths
            ),
            "remover": self.dialog._windows_ocr_remover_script(
                codes, capabilities, *paths
            ),
        }

    def test_no_block_lost_its_braces_to_the_f_string(self):
        for name, script in self._scripts().items():
            # Every if/else/foreach opens a block, so each keyword must be
            # followed by a brace on the same line.
            for match in re.finditer(
                r"^[^\S\n]*(?:\}[^\S\n]*)?(if \(|elseif \(|foreach \(|else\b)", script, re.M
            ):
                start = match.start(1)
                line = script[start:script.index("\n", start)]
                self.assertIn("{", line, f"{name}: {line.strip()}")

    def test_the_restart_result_is_written_as_powershell_not_as_text(self):
        """The exact line that broke: its braces were eaten, so the literals
        were spliced in bare and the file stopped parsing."""
        installer = self._scripts()["installer"]

        self.assertIn("'OK_RESTART'", installer)
        self.assertNotIn(") OK_RESTART else OK", installer)

    @unittest.skipUnless(sys.platform == "win32", "the PowerShell parser is Windows only")
    def test_powershell_itself_accepts_them(self):
        import subprocess
        import tempfile

        for name, script in self._scripts().items():
            handle = tempfile.NamedTemporaryFile(
                "w", suffix=".ps1", delete=False, encoding="utf-8"
            )
            try:
                handle.write(script)
                handle.close()
                command = (
                    "$errors = $null; "
                    "[void][System.Management.Automation.Language.Parser]::ParseFile("
                    f"'{handle.name}', [ref]$null, [ref]$errors); "
                    "if ($errors.Count) { $errors | ForEach-Object { $_.ToString() }; exit 1 }"
                )
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
            finally:
                os.unlink(handle.name)
            self.assertEqual(
                completed.returncode,
                0,
                f"{name} does not parse:\n{completed.stdout}",
            )




if __name__ == "__main__":
    unittest.main()
