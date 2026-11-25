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
        self.stage = "device"
        self.verified = False
        self.last_xml = b""

    def run(self, *args):
        return subprocess.run(self.adb + list(args), check=True, capture_output=True, timeout=20).stdout

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

    def screen(self, stage, expected, action=None, completed=False):
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
            point = action_point(tree, self.package, action) if action else None
            if set(expected) <= visible and (action is None or point):
                (self.output / f"{stage}.xml").write_bytes(self.last_xml)
                self.stages.append(stage)
                if point:
                    self.tap(point)
                return
            detail = f"visible labels: {sorted(visible)!r}"
            time.sleep(0.4)
        raise RuntimeError(f"Timed out waiting for {expected!r}, action {action!r}; {detail}")

    def launch(self):
        result = self.run("shell", "am", "start", "-W", "-a", "android.intent.action.MAIN",
                          "-c", "android.intent.category.LAUNCHER", "-p", self.package)
        if b"Error:" in result or b"Status: ok" not in result:
            raise RuntimeError("Failed to open the package's launcher activity")

    def execute(self):
        if self.run("shell", "getprop", "ro.kernel.qemu").strip() != b"1":
            raise ValueError("This command requires an Android Emulator")
        if self.run("shell", "getprop", "ro.build.version.sdk").strip() != b"35":
            raise ValueError("This journey targets the English API 35 AVD")
        self.verified = True
        self.launch()
        for index, title in enumerate(STEPS, start=1):
            self.screen(f"step-{index}", (f"Step {index} of 4", title),
                        "Continue" if index < 4 else "Finish setup")
        home = ("Understand anything.", "Text", "History", "Settings")
        self.screen("home", home, "Settings")
        self.screen("settings", ("Offline engines and packages", "Settings"))
        self.stage = "cold-launch"
        self.run("shell", "am", "force-stop", self.package)
        self.launch()
        self.screen("shell-after-restart", ("Screen", "Text", "History", "Settings"), "Screen", completed=True)
        self.screen("home-after-restart", home, completed=True)
        (self.output / "home-after-restart.png").write_bytes(self.run("exec-out", "screencap", "-p"))

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
    report = {"serial": args.serial, "package": args.package, "stages": journey.stages}
    try:
        journey.execute()
        report["passed"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(passed=False, failedStage=journey.stage, error=str(error))
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
