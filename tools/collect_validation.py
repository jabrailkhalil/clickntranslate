"""Collect completed Gradle/JUnit/Android runs without treating skipped tests as passed."""
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    data = path.read_bytes()
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def instrumentation_seconds(content):
    # JUnit's NumberFormat adds grouping after999s. Captured diagnostic dumps can
    # also contain an earlier '*Time:' field; only the final full footer is ours.
    elapsed = re.findall(r"^Time: ((?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?)\s*$", content, re.MULTILINE)
    if not elapsed:
        raise ValueError("Missing JUnit elapsed-time footer")
    return float(elapsed[-1].replace(",", ""))


def instrumentation(path):
    content = read(path)
    cases, current = [], {}
    names = {"0": "passed", "-4": "skipped", "-3": "skipped", "-2": "failed", "-1": "failed"}
    for line in content.splitlines():
        match = re.fullmatch(r"INSTRUMENTATION_STATUS: (class|test)=(.*)", line)
        if match:
            current[match[1]] = match[2]
        code = re.fullmatch(r"INSTRUMENTATION_STATUS_CODE: (-?\d+)", line)
        if code and code[1] in names:
            if not {"class", "test"} <= current.keys():
                raise ValueError(f"Missing test identity: {path}")
            cases.append(dict(current, result=names[code[1]]))
    if not re.search(r"OK \(\d+ tests?\)", content) or "FAILURES!!!" in content:
        raise ValueError(f"Android run did not complete successfully: {path}")
    if not cases or any(case["result"] == "failed" for case in cases):
        raise ValueError(f"Missing or failing Android cases: {path}")
    declared = {int(n) for n in re.findall(r"INSTRUMENTATION_STATUS: numtests=(\d+)", content)}
    if declared != {len(cases)}:
        raise ValueError(f"Incomplete Android run: {path}, declared={declared}, finished={len(cases)}")
    return {"log": path.as_posix(), "sha256": digest(path), "tests": len(cases),
            "passed": sum(c["result"] == "passed" for c in cases),
            "skipped": sum(c["result"] == "skipped" for c in cases), "failed": 0,
            "seconds": instrumentation_seconds(content), "cases": cases}


def unit(directory):
    suites = []
    for path in sorted(directory.glob("TEST-*.xml")):
        root = ET.parse(path).getroot()
        values = {key: int(root.attrib.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")}
        suites.append(dict(name=root.attrib["name"], sha256=digest(path), **values))
    if not suites or any(s["failures"] or s["errors"] for s in suites):
        raise ValueError(f"Missing or failing unit suites: {directory}")
    return {"directory": directory.as_posix(), **{
        key: sum(s[key] for s in suites) for key in ("tests", "failures", "errors", "skipped")}, "suites": suites}


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def run_source(path, reference):
    source = json.loads(read(path))
    commit = source["implementation_commit"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError(f"Expected a full source commit: {path}")
    tree = git("rev-parse", f"{commit}:app")
    if tree != source["application_tree"]:
        raise ValueError(f"Source manifest does not match Git: {path}")
    changed = git("diff", "--name-only", commit, reference, "--", "app", "build.gradle.kts",
                  "settings.gradle.kts", "gradle.properties", "gradle", "gradlew", "gradlew.bat").splitlines()
    if any(not name.startswith("app/src/androidTest/") for name in changed):
        raise ValueError(f"A different target implementation cannot share this report: {path}")
    return {"manifest": path.as_posix(), "sha256": digest(path), "implementation_commit": commit,
            "application_tree": tree, "target_inputs_unchanged": True,
            "artifact_hashes": {re.split(r"[/\\]", item["Path"])[-1]: item["Hash"].lower()
                                for item in source["artifacts"]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-dir", type=Path, action="append", required=True)
    parser.add_argument("--android", action="append", default=[], help="name=instrumentation-log")
    parser.add_argument("--android-source", action="append", default=[], help="name=exact-APK-source-manifest; target inputs must match, Android test fixtures may differ")
    parser.add_argument("--build-log", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if git("status", "--porcelain", "--", "app"):
        raise ValueError("Commit the exact built application sources before collecting validation")
    reference = git("rev-parse", "HEAD")
    android = {name: instrumentation(Path(path)) for name, path in (v.split("=", 1) for v in args.android)}
    sources = dict(value.split("=", 1) for value in args.android_source)
    if len(sources) != len(args.android_source) or not sources.keys() <= android.keys():
        raise ValueError("Every source override must identify one existing Android run exactly once")
    for name, path in sources.items():
        android[name]["source"] = run_source(Path(path), reference)
    builds = []
    for path in args.build_log:
        if "BUILD SUCCESSFUL" not in read(path) or "BUILD FAILED" in read(path):
            raise ValueError(f"Unsuccessful Gradle run: {path}")
        builds.append({"log": path.as_posix(), "sha256": digest(path), "result": "BUILD SUCCESSFUL"})
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "implementation_commit": reference, "application_tree": git("rev-parse", "HEAD:app"),
              "branch": git("branch", "--show-current"), "working_tree_dirty": bool(git("status", "--porcelain")),
              "application_working_tree_dirty": False,
              "scope_complete": False, "physical_arm64_device_tested": False, "builds": builds,
              "unit": [unit(path) for path in args.unit_dir],
              "android": android}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"units": sum(r["tests"] for r in report["unit"]),
                      "android": {k: {f: v[f] for f in ("tests", "passed", "skipped", "failed")} for k, v in report["android"].items()}}, indent=2))
