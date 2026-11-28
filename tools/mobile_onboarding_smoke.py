"""Exercise a fresh English Click'n'Translate install on a disposable API 35 AVD."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


STEPS = ("Interface language", "Choose a theme", "Choose your companion", "Languages and translation")
HOME_TITLE = "Understand anything."
PERMISSION_PACKAGES = {"com.android.permissioncontroller", "com.google.android.permissioncontroller"}


def labels(node):
    return {
        line.strip()
        for attribute in ("text", "content-desc")
        for line in node.get(attribute, "").splitlines()
        if line.strip()
    }


def center(node):
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if match:
        left, top, right, bottom = map(int, match.groups())
        if right > left and bottom > top:
            return (left + right) // 2, (top + bottom) // 2
    return None


def action_point(tree, package, label):
    parents = {child: parent for parent in tree.iter() for child in parent}
    for node in tree.iter("node"):
        if node.get("package") != package or label not in labels(node):
            continue
        while node is not None and node.get("package") == package:
            if node.get("enabled") == "false":
                break
            if node.get("clickable") == "true" and center(node):
                return center(node)
            node = parents.get(node)
    return None


class Journey:
    def __init__(self, args):
        self.adb = [args.adb, "-s", args.serial]
        self.package = args.package
        self.output = args.output
        self.remote = f"/data/local/tmp/clickntranslate-onboarding-{os.getpid()}.xml"
        self.stages = []
        self.launches = []
        self.stage = "device"
        self.verified = False
        self.last_xml = b""
        self.installed_version = ""

    def run(self, *args):
        cmd = self.adb + list(args)
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode:
            with (self.output / "adb-errors.log").open("a", encoding="utf-8") as log:
                print(f"{self.stage}: {cmd!r} exited {result.returncode}", file=log)
                print("stdout:", result.stdout.decode(errors="replace"), file=log)
                print("stderr:", result.stderr.decode(errors="replace"), file=log)
            result.check_returncode()
        return result.stdout

    def read_tree(self):
        result = self.run("shell", "uiautomator", "dump", self.remote)
        if b"dumped to:" not in result.lower():
            raise RuntimeError("Could not read the current Android accessibility tree")
        xml = self.run("exec-out", "cat", self.remote)
        tree = ET.fromstring(xml)
        self.last_xml = xml
        return tree

    def tap(self, point):
        self.run("shell", "input", "tap", *(str(n) for n in point))

    def dismiss_notifications(self, tree):
        nodes = [node for node in tree.iter("node") if node.get("package") in PERMISSION_PACKAGES]
        if any("notification" in text.lower() for node in nodes for text in labels(node)):
            for node in nodes:
                if node.get("resource-id", "").endswith(":id/permission_deny_button") and center(node):
                    self.tap(center(node))
                    return True
        return False

    def screen(self, stage, expected, action=None, completed=False, skip_action_when_visible=None):
        self.stage = stage
        deadline = time.monotonic() + 60
        detail = ""
        while time.monotonic() < deadline:
            try:
                tree = self.read_tree()
            except (RuntimeError, ET.ParseError, subprocess.SubprocessError) as error:
                detail = str(error)
                time.sleep(0.4)
                continue
            if self.dismiss_notifications(tree):
                continue
            visible = {text for node in tree.iter("node") if node.get("package") == self.package
                       and center(node) for text in labels(node)}
            if completed and "Set up your translator" in visible:
                raise RuntimeError("The setup wizard returned after a cold start")
            needs_tap = action is not None and skip_action_when_visible not in visible
            point = action_point(tree, self.package, action) if needs_tap else None
            if set(expected) <= visible and (not needs_tap or point):
                if stage != "help-version" and any(self.installed_version in label for label in visible):
                    raise RuntimeError(f"Installed version appeared outside help on {stage}")
                (self.output / f"{stage}.xml").write_bytes(self.last_xml)
                if stage in {"step-1", "step-3", "settings", "os-language-french", "help-version"}:
                    (self.output / f"{stage}.png").write_bytes(self.run("exec-out", "screencap", "-p"))
                self.stages.append(stage)
                if point:
                    self.tap(point)
                return
            detail = f"visible labels: {sorted(visible)!r}"
            time.sleep(0.4)
        raise RuntimeError(f"Timed out waiting for {expected!r}, action {action!r}; {detail}")

    def launch(self):
        intent = ("-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER")
        # A launcher starts the enabled component. This app exposes a different alias for each icon.
        resolved = self.run("shell", "cmd", "package", "resolve-activity", "--components",
                            "--user", "current", *intent, "-p", self.package).decode(errors="replace").strip()
        (self.output / f"{self.stage}-component.txt").write_text(resolved + "\n", encoding="utf-8")
        if not re.fullmatch(re.escape(self.package) + r"/[A-Za-z_.$][\w.$]*", resolved):
            raise RuntimeError(f"No active launcher component for {self.package}: {resolved!r}")
        result = self.run("shell", "am", "start", "-W", "--user", "current", *intent,
                          "-f", "0x10200000", "-n", resolved)
        (self.output / f"{self.stage}-activity.txt").write_bytes(result)
        if b"Error:" in result or b"Status: ok" not in result:
            raise RuntimeError(f"Failed to open {resolved}: {result.decode(errors='replace').strip()}")
        metrics = {"stage": self.stage, "component": resolved}
        for key, value in re.findall(r"^(LaunchState|TotalTime|WaitTime):\s*([^\r\n]+)", result.decode(), re.MULTILINE):
            metrics[key] = int(value) if value.isdecimal() else value.strip()
        self.launches.append(metrics)

    def execute(self):
        if self.run("shell", "getprop", "ro.kernel.qemu").strip() != b"1":
            raise ValueError("This command requires an Android Emulator")
        if self.run("shell", "getprop", "ro.build.version.sdk").strip() != b"35":
            raise ValueError("This journey targets the English API 35 AVD")
        self.verified = True
        package = self.run("shell", "dumpsys", "package", self.package).decode()
        version = re.search(r"^\s*versionName=(\S+)", package, re.M)
        if not version:
            raise RuntimeError("Android did not report the installed application version")
        self.installed_version = version[1]
        self.stage = "first-launch"
        self.launch()
        for index, title in enumerate(STEPS, start=1):
            self.screen(f"step-{index}", (f"Step {index} of 4", title),
                        "Continue" if index < 4 else "Finish setup")
        home = (HOME_TITLE, "Text", "History", "Settings")
        self.screen("home", home, "Settings")
        self.screen("settings", ("Offline engines and packages", "Settings"))
        self.stage = "cold-launch"
        self.run("shell", "am", "force-stop", self.package)
        self.launch()
        self.screen("shell-after-restart", ("Screen", "Text", "History", "Settings"), "Screen",
                    completed=True, skip_action_when_visible=HOME_TITLE)
        self.screen("home-after-restart", home, completed=True)
        (self.output / "home-after-restart.png").write_bytes(self.run("exec-out", "screencap", "-p"))
        self.check_system_app_language(home)
        self.screen("open-help", home, "How it works", completed=True)
        self.screen("help-version", ("Set up your translator", f"Version {self.installed_version}"))
        self.run("shell", "am", "force-stop", self.package)

    def check_system_app_language(self, english_home):
        # The first-run fixture left the in-app language at Follow system. This changes
        # Android's per-package setting without invoking the application's language picker.
        self.stage = "read-os-language"
        get_command = ("shell", "cmd", "locale", "get-app-locales", self.package)
        set_command = ("shell", "cmd", "locale", "set-app-locales", self.package)
        saved = re.search(r"\[([^\]]*)\]", self.run(*get_command).decode())
        if saved is None:
            raise RuntimeError("Android did not report the current app language")
        french_home = ("Tout comprendre.", "Texte", "Historique", "Réglages")
        try:
            self.run(*set_command, "--locales", "fr")
            if b"[fr]" not in self.run(*get_command):
                raise RuntimeError("Android did not select French for the test app")
            self.screen("os-language-french", french_home, completed=True)
            self.stage = "os-language-cold-launch"
            self.run("shell", "am", "force-stop", self.package)
            self.launch()
            self.screen("os-language-cold-home", french_home, completed=True)
        except (OSError, RuntimeError, ET.ParseError, subprocess.SubprocessError):
            if self.last_xml:
                (self.output / "os-language-failure.xml").write_bytes(self.last_xml)
            try:
                (self.output / "os-language-failure.png").write_bytes(self.run("exec-out", "screencap", "-p"))
            except (OSError, subprocess.SubprocessError):
                pass
            raise
        finally:
            restore = ("--locales", saved.group(1)) if saved.group(1) else ()
            self.run(*set_command, *restore)
        self.screen("os-language-restored", english_home, completed=True)

    def failure_evidence(self):
        if self.verified:
            try:
                self.read_tree()
            except (OSError, RuntimeError, ET.ParseError, subprocess.SubprocessError):
                if self.last_xml:
                    (self.output / "last-observed.xml").write_bytes(self.last_xml)
            else:
                (self.output / "failure.xml").write_bytes(self.last_xml)
            try:
                (self.output / "failure.png").write_bytes(self.run("exec-out", "screencap", "-p"))
            except (OSError, subprocess.SubprocessError):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="Serial of the disposable emulator, e.g. emulator-5554")
    parser.add_argument("--package", default="dev.clickn.translate.debug", choices=[
        "dev.clickn.translate", "dev.clickn.translate.debug", "dev.clickn.translate.preview", "dev.clickn.translate.validation",
    ])
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"emulator-\d+", args.serial):
        parser.error("--serial must identify a disposable emulator-NNNN")
    args.output.mkdir(parents=True, exist_ok=True)
    journey = Journey(args)
    report = {"serial": args.serial, "package": args.package, "stages": journey.stages, "launches": journey.launches}
    try:
        journey.execute()
        report["passed"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        detail = ""
        if isinstance(error, subprocess.CalledProcessError):
            detail = (error.stderr or error.stdout or b"").decode(errors="replace").strip()
        report.update(passed=False, failedStage=journey.stage, error=f"{error}\n{detail}".strip())
        journey.failure_evidence()
    finally:
        if journey.verified:
            try:
                journey.run("shell", "rm", "-f", journey.remote)
            except (OSError, subprocess.SubprocessError):
                pass
        (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
