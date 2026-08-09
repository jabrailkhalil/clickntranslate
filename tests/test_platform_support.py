import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402
import portable_paths  # noqa: E402


class ExecutableNamingTest(unittest.TestCase):
    def test_helper_executables_use_the_platform_suffix(self):
        expected = "ArgosWorker.exe" if platform_support.IS_WINDOWS else "ArgosWorker"
        self.assertEqual(platform_support.executable_name("ArgosWorker"), expected)

    def test_exactly_one_platform_flag_is_set(self):
        flags = [platform_support.IS_WINDOWS, platform_support.IS_LINUX, platform_support.IS_MAC]
        self.assertLessEqual(sum(1 for flag in flags if flag), 1)


class SessionDetectionTest(unittest.TestCase):
    def test_session_type_prefers_the_explicit_variable(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=False):
                self.assertEqual(platform_support.linux_session_type(), "wayland")
                self.assertTrue(platform_support.is_wayland())

    def test_session_type_falls_back_to_display_variables(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {}, clear=True):
                os.environ["DISPLAY"] = ":0"
                self.assertEqual(platform_support.linux_session_type(), "x11")
                self.assertFalse(platform_support.is_wayland())

    def test_session_type_is_empty_without_a_display(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(platform_support.linux_session_type(), "")
                self.assertFalse(platform_support.has_display())

    def test_desktop_environment_reads_a_colon_separated_list(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, clear=True):
                self.assertEqual(platform_support.desktop_environment(), "gnome")

    def test_plasma_is_reported_as_kde(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE:plasma"}, clear=True):
                self.assertEqual(platform_support.desktop_environment(), "kde")


class SubprocessFlagsTest(unittest.TestCase):
    def test_windows_hides_the_console_and_other_systems_need_nothing(self):
        kwargs = platform_support.no_window_kwargs()
        if platform_support.IS_WINDOWS:
            self.assertIn("startupinfo", kwargs)
            self.assertIn("creationflags", kwargs)
        else:
            self.assertEqual(kwargs, {})

    def test_system_subprocess_environment_removes_only_bundled_linux_paths(self):
        appdir = os.path.abspath(os.path.join(os.sep, "tmp", "clickntranslate.AppDir"))
        bundled = os.path.join(appdir, "usr", "bin", "_internal")
        system_path = os.path.abspath(os.path.join(os.sep, "opt", "user-libs"))
        inherited = os.pathsep.join((bundled, system_path))
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(
                os.environ,
                {"APPDIR": appdir, "LD_LIBRARY_PATH": inherited, "DISPLAY": ":0"},
                clear=True,
            ):
                child_env = platform_support.system_subprocess_env()
                self.assertEqual(child_env["LD_LIBRARY_PATH"], system_path)
                self.assertEqual(child_env["DISPLAY"], ":0")
                self.assertEqual(os.environ["LD_LIBRARY_PATH"], inherited)

    def test_system_subprocess_environment_drops_an_entire_bundled_value(self):
        appdir = os.path.abspath(os.path.join(os.sep, "tmp", "clickntranslate.AppDir"))
        bundled = os.path.join(appdir, "usr", "bin", "_internal")
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(
                os.environ,
                {"APPDIR": appdir, "LD_LIBRARY_PATH": bundled},
                clear=True,
            ):
                self.assertNotIn(
                    "LD_LIBRARY_PATH",
                    platform_support.system_subprocess_env(),
                )


class XdgDirectoryTest(unittest.TestCase):
    def test_environment_override_is_used_when_absolute(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": os.path.abspath(os.sep + "cfg")}, clear=False):
            self.assertEqual(platform_support.xdg_config_home(), os.path.abspath(os.sep + "cfg"))

    def test_relative_override_is_ignored(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "relative/path"}, clear=False):
            self.assertEqual(
                platform_support.xdg_data_home(),
                os.path.join(os.path.expanduser("~"), ".local", "share"),
            )

    def test_autostart_and_applications_live_under_xdg(self):
        base = os.path.abspath(os.sep + "xdgcfg")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": base}, clear=False):
            self.assertEqual(platform_support.autostart_dir(), os.path.join(base, "autostart"))


class ShortcutCommandTest(unittest.TestCase):
    def test_every_windows_hotkey_action_has_a_shortcut_action(self):
        self.assertEqual(
            set(platform_support.SHORTCUT_ACTIONS),
            {"ocr", "copy", "translate", "fullscreen", "selection", "toggle"},
        )

    def test_command_uses_the_appimage_path_when_running_from_one(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"APPIMAGE": "/opt/Click-n-Translate.AppImage"}, clear=False):
                self.assertEqual(
                    platform_support.shortcut_command("ocr"),
                    "/opt/Click-n-Translate.AppImage --ocr",
                )

    def test_paths_with_spaces_are_quoted(self):
        command = platform_support.shortcut_command("copy", executable="/home/a b/clickntranslate")
        self.assertEqual(command, '"/home/a b/clickntranslate" --copy')

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            platform_support.shortcut_command("launch-nukes")


class OcrEngineAvailabilityTest(unittest.TestCase):
    def test_windows_ocr_is_offered_on_windows_only(self):
        self.assertEqual(platform_support.supports_windows_ocr(), platform_support.IS_WINDOWS)
        self.assertEqual("windows" in platform_support.available_ocr_engines(), platform_support.IS_WINDOWS)

    def test_linux_defaults_to_tesseract(self):
        self.assertEqual(platform_support.LINUX_OCR_ENGINES[0], "tesseract")
        self.assertNotIn("windows", platform_support.LINUX_OCR_ENGINES)

    def test_install_hint_matches_the_package_manager(self):
        with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/dnf" if name == "dnf" else None):
            self.assertIn("dnf install", platform_support.tesseract_install_hint())

    def test_install_hint_falls_back_to_debian(self):
        with mock.patch.object(platform_support.shutil, "which", return_value=None):
            self.assertIn("apt install", platform_support.tesseract_install_hint())


class UpdatePolicyTest(unittest.TestCase):
    def test_self_replacement_is_windows_only(self):
        self.assertEqual(platform_support.supports_in_app_update(), platform_support.IS_WINDOWS)


class LinuxPortableBaseDirTest(unittest.TestCase):
    def test_appimage_keeps_user_data_in_xdg(self):
        data_home = os.path.abspath(os.sep + "home" + os.sep + "u" + os.sep + "data")
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"APPIMAGE": "/opt/app.AppImage", "XDG_DATA_HOME": data_home}, clear=False):
                self.assertEqual(
                    portable_paths.portable_base_dir(),
                    os.path.join(data_home, portable_paths.LINUX_DATA_DIR_NAME),
                )

    def test_frozen_tarball_stays_portable_when_writable(self, ):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(portable_paths.sys, "frozen", True, create=True):
                    with mock.patch.object(portable_paths, "is_internal_worker_layout", return_value=False):
                        with mock.patch.object(portable_paths, "frozen_executable_dir", return_value=str(ROOT)):
                            with mock.patch.object(portable_paths, "_is_writable_dir", return_value=True):
                                self.assertEqual(portable_paths.portable_base_dir(), str(ROOT))

    def test_internal_worker_resolves_the_application_root(self):
        """A helper in _internal must use the app folder, not its own."""
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(portable_paths.sys, "frozen", True, create=True):
                    with mock.patch.object(portable_paths, "is_internal_worker_layout", return_value=True):
                        with mock.patch.object(
                            portable_paths,
                            "_internal_worker_portable_root",
                            return_value="/opt/clickntranslate",
                        ):
                            with mock.patch.object(portable_paths, "_is_writable_dir", return_value=True):
                                self.assertEqual(
                                    portable_paths.portable_base_dir(), "/opt/clickntranslate"
                                )

    def test_appimage_is_the_executable_a_shortcut_should_launch(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"APPIMAGE": "/opt/Click-n-Translate.AppImage"}, clear=False):
                self.assertEqual(
                    portable_paths.public_executable_path(),
                    os.path.abspath("/opt/Click-n-Translate.AppImage"),
                )

    def test_read_only_install_falls_back_to_xdg(self):
        data_home = os.path.abspath(os.sep + "home" + os.sep + "u" + os.sep + "data")
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data_home}, clear=True):
                with mock.patch.object(portable_paths.sys, "frozen", True, create=True):
                    with mock.patch.object(portable_paths, "is_internal_worker_layout", return_value=False):
                        with mock.patch.object(portable_paths, "frozen_executable_dir", return_value="/usr/lib/clickntranslate"):
                            with mock.patch.object(portable_paths, "_is_writable_dir", return_value=False):
                                self.assertEqual(
                                    portable_paths.portable_base_dir(),
                                    os.path.join(data_home, portable_paths.LINUX_DATA_DIR_NAME),
                                )


if __name__ == "__main__":
    unittest.main()
