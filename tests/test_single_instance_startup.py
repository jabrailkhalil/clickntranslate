"""Exercise the actual Linux startup branch without loading Qt or OCR models."""

import ast
import logging
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import single_instance


class LinuxForwardingStartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.BoolOp)
                      and ast.unparse(n.test) == "(platform_support.IS_LINUX or platform_support.IS_MAC) and (not LAYOUT_EDITOR_MODE)")
        module = ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[]))
        cls.code = compile(module, str(ROOT / "main.py"), "exec")

    def launch(self, statuses, bind=True, action='ocr', autostart=False, replace=True):
        state = {"platform_support": mock.Mock(IS_LINUX=True), "LAYOUT_EDITOR_MODE": False,
                 "sys": sys, "logging": logging, "_requested_shortcut_action": action,
                 "_main_window_ref": None, "_command_server": None,
                 "_started_from_autostart": mock.Mock(return_value=autostart),
                 "_replace_existing_instance": mock.Mock(return_value=replace),
                 "invalidate_config_cache": mock.Mock(),
                 "_show_instance_replacement_error": mock.Mock()}
        self.state = state
        self.forward = mock.patch.object(single_instance, "send_command_status", side_effect=statuses).start()
        self.addCleanup(mock.patch.stopall)
        self.factory = mock.patch.object(single_instance, "CommandServer").start()
        if isinstance(bind, list):
            self.factory.return_value.bind.side_effect = bind
        else:
            self.factory.return_value.bind.return_value = bind
        with mock.patch("sys.stderr"):
            exec(self.code, state)
        return state

    def test_manual_launch_can_replace_and_claim_the_released_channel(self):
        state = self.launch([single_instance.CommandStatus.ACCEPTED], action='')
        state['_replace_existing_instance'].assert_called_once_with()
        state['invalidate_config_cache'].assert_called_once_with()
        self.factory.return_value.start.assert_called_once_with()

    def test_manual_cancel_and_autostart_keep_the_old_instance(self):
        for autostart in (False, True):
            with self.subTest(autostart=autostart), self.assertRaises(SystemExit) as result:
                self.launch([single_instance.CommandStatus.ACCEPTED], action='',
                            autostart=autostart, replace=False)
            self.assertEqual(result.exception.code, 0)
            self.assertEqual(self.state['_replace_existing_instance'].call_count, 0 if autostart else 1)
            self.factory.assert_not_called()
            mock.patch.stopall()

    def test_manual_startup_race_still_offers_the_same_choice(self):
        state = self.launch([single_instance.CommandStatus.UNAVAILABLE, single_instance.CommandStatus.ACCEPTED],
                            action='', bind=[False, True])
        state['_replace_existing_instance'].assert_called_once_with()
        self.factory.return_value.start.assert_called_once_with()

    def test_acknowledged_command_exits_successfully_without_new_server(self):
        with self.assertRaises(SystemExit) as result:
            self.launch([single_instance.CommandStatus.ACCEPTED])
        self.assertEqual(result.exception.code, 0)
        self.factory.assert_not_called()

    def test_busy_or_ambiguous_delivery_does_not_start_or_replay(self):
        for status in (single_instance.CommandStatus.BUSY, single_instance.CommandStatus.FAILED):
            with self.subTest(status=status), self.assertLogs(level="ERROR"):
                with self.assertRaises(SystemExit) as result:
                    self.launch([status])
                self.assertEqual(result.exception.code, 75)
                self.forward.assert_called_once()
                self.factory.assert_not_called()
            mock.patch.stopall()

    def test_new_owner_buffers_commands_until_ui_ready(self):
        self.launch([single_instance.CommandStatus.UNAVAILABLE])
        self.assertFalse(self.factory.call_args.kwargs["start_ready"])
        self.factory.return_value.start.assert_called_once()
        self.factory.return_value.set_ready.assert_not_called()
        ready_at = self.source.index("_command_server.set_ready()")
        self.assertGreater(ready_at, self.source.index("_main_window_ref = window"))

    def test_lost_ownership_race_can_forward_previously_unsent_command(self):
        with self.assertRaises(SystemExit) as result:
            self.launch([single_instance.CommandStatus.UNAVAILABLE, single_instance.CommandStatus.ACCEPTED], bind=False)
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(self.forward.call_count, 2)
        self.factory.return_value.start.assert_not_called()

    def test_failed_race_forward_is_not_silent_success(self):
        with self.assertLogs(level="ERROR"), self.assertRaises(SystemExit) as result:
            self.launch([single_instance.CommandStatus.UNAVAILABLE, single_instance.CommandStatus.BUSY], bind=False)
        self.assertEqual(result.exception.code, 75)
        self.factory.return_value.start.assert_not_called()

    def test_application_shutdown_stops_and_joins_channel(self):
        tree = ast.parse(self.source)
        shutdown = next(n.finalbody for n in ast.walk(tree) if isinstance(n, ast.Try)
                        and any(isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                                and ast.unparse(item.value.func) == "app.exec_" for item in n.body))
        code = compile(ast.fix_missing_locations(ast.Module(body=shutdown, type_ignores=[])),
                       str(ROOT / "main.py"), "exec")
        server = mock.Mock()
        exec(code, {"_command_server": server})
        self.assertEqual(server.mock_calls, [mock.call.stop(), mock.call.join(timeout=2.0)])
        exec(code, {"_command_server": None})


if __name__ == "__main__":
    unittest.main()
